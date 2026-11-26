#!/usr/bin/env python3
"""Kushagra OS First-Boot Setup Wizard (OOBE) Qt6/QML Application."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
RESERVED_USERS = {"root", "liveuser", "kushagra-oobe", "plasma-setup", "nobody"}


def scan_wifi_networks():
    """Query NetworkManager via nmcli for available Wi-Fi networks and connection state."""
    if not shutil.which("nmcli"):
        return [], "NetworkManager CLI unavailable"

    connected_desc = ""
    try:
        dev_res = subprocess.run(
            ["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "dev", "status"],
            capture_output=True, text=True, timeout=6
        )
        for line in dev_res.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) == 3 and parts[1].startswith("connected"):
                connected_desc = f"{parts[0]}: {parts[2]}"
                break
    except Exception:
        pass

    networks = []
    seen = set()
    try:
        # Trigger lightweight rescan (best-effort)
        subprocess.run(["nmcli", "dev", "wifi", "rescan"], capture_output=True, timeout=5)
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
            capture_output=True, text=True, timeout=8
        )
        for line in res.stdout.splitlines():
            parts = line.split(":")
            if len(parts) < 4:
                continue
            in_use = parts[0].strip() == "*"
            ssid = parts[1].strip()
            signal_str = parts[2].strip()
            security = ":".join(parts[3:]).strip()
            if not ssid or ssid in seen:
                continue
            seen.add(ssid)
            try:
                signal = int(signal_str)
            except ValueError:
                signal = 0
            networks.append({
                "ssid": ssid,
                "signal": signal,
                "security": security if security else "Open",
                "secured": bool(security and security != "--"),
                "connected": in_use,
            })
        networks.sort(key=lambda item: (not item["connected"], -item["signal"]))
    except Exception as exc:
        return [], f"Wi-Fi scan error: {exc}"

    return networks, connected_desc


class WifiWorker(QThread):
    """Non-blocking background worker for Wi-Fi scan and connection operations."""

    scanFinished = pyqtSignal(list, str)
    connectFinished = pyqtSignal(bool, str)

    def __init__(self, mode="scan", ssid="", password="", parent=None):
        super().__init__(parent)
        self.mode = mode
        self.ssid = ssid
        self.password = password

    def run(self):
        if self.mode == "scan":
            nets, status = scan_wifi_networks()
            self.scanFinished.emit(nets, status)
        elif self.mode == "connect":
            if not shutil.which("nmcli"):
                self.connectFinished.emit(False, "nmcli not available")
                return
            cmd = ["nmcli", "dev", "wifi", "connect", self.ssid]
            if self.password:
                cmd.extend(["password", self.password])
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
                if res.returncode == 0:
                    self.connectFinished.emit(True, f"Connected to {self.ssid}")
                else:
                    msg = (res.stderr or res.stdout or "Connection failed").strip()
                    self.connectFinished.emit(False, msg)
            except Exception as exc:
                self.connectFinished.emit(False, str(exc))


class ApplyWorker(QThread):
    """Background worker executing privileged OOBE system finalization."""

    finishedApply = pyqtSignal(bool, str)

    def __init__(self, payload: dict, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.preview_mode = preview_mode

    def run(self):
        if self.preview_mode:
            self.msleep(1000)
            self.finishedApply.emit(True, "Preview mode completed (no system changes made).")
            return

        apply_helper = "/usr/libexec/kushagra-oobe-apply"
        if not os.path.exists(apply_helper):
            self.finishedApply.emit(False, f"Missing backend helper: {apply_helper}")
            return

        try:
            res = subprocess.run(
                ["pkexec", apply_helper],
                input=json.dumps(self.payload),
                text=True,
                capture_output=True,
                timeout=60,
            )
            if res.returncode == 0:
                self.finishedApply.emit(True, "Setup complete. Launching desktop...")
            else:
                msg = (res.stderr or res.stdout or f"Setup failed (exit {res.returncode})").strip()
                self.finishedApply.emit(False, msg)
        except Exception as exc:
            self.finishedApply.emit(False, str(exc))


class OobeBackend(QObject):
    """Bridge exposing validated system actions and state to Main.qml."""

    wifiListChanged = pyqtSignal()
    wifiBusyChanged = pyqtSignal()
    wifiStatusChanged = pyqtSignal()
    applyBusyChanged = pyqtSignal()
    setupErrorChanged = pyqtSignal()
    setupCompleted = pyqtSignal()

    def __init__(self, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.preview_mode = preview_mode
        self._wifi_list = []
        self._wifi_busy = False
        self._wifi_status = ""
        self._apply_busy = False
        self._setup_error = ""
        self._workers = []

    @pyqtProperty(list, notify=wifiListChanged)
    def wifiList(self):
        return self._wifi_list

    @pyqtProperty(bool, notify=wifiBusyChanged)
    def wifiBusy(self):
        return self._wifi_busy

    @pyqtProperty(str, notify=wifiStatusChanged)
    def wifiStatus(self):
        return self._wifi_status

    @pyqtProperty(bool, notify=applyBusyChanged)
    def applyBusy(self):
        return self._apply_busy

    @pyqtProperty(str, notify=setupErrorChanged)
    def setupError(self):
        return self._setup_error

    @pyqtSlot(str, result=str)
    def suggestUsername(self, fullname: str) -> str:
        """Sanitize full name into a valid POSIX username suggestion."""
        cleaned = re.sub(r"[^a-z0-9_-]", "", fullname.strip().lower().replace(" ", ""))
        cleaned = re.sub(r"^[^a-z_]+", "", cleaned)[:24]
        return cleaned

    @pyqtSlot(str, result=str)
    def validateUsername(self, username: str) -> str:
        """Return empty string when valid, or concise validation message."""
        u = username.strip()
        if not u:
            return "Username is required."
        if not USERNAME_RE.match(u):
            return "Use lowercase letters, numbers, '-' or '_' starting with a letter."
        if u in RESERVED_USERS:
            return f"'{u}' is reserved by the system."
        return ""

    @pyqtSlot()
    def scanWifi(self):
        if self._wifi_busy:
            return
        self._wifi_busy = True
        self.wifiBusyChanged.emit()
        worker = WifiWorker(mode="scan", parent=self)
        worker.scanFinished.connect(self._on_scan_done)
        self._workers.append(worker)
        worker.start()

    def _on_scan_done(self, nets, status):
        self._wifi_list = nets
        self._wifi_status = status
        self._wifi_busy = False
        self.wifiListChanged.emit()
        self.wifiStatusChanged.emit()
        self.wifiBusyChanged.emit()

    @pyqtSlot(str, str)
    def connectWifi(self, ssid: str, password: str):
        if self._wifi_busy or not ssid:
            return
        self._wifi_busy = True
        self._wifi_status = f"Connecting to {ssid}..."
        self.wifiBusyChanged.emit()
        self.wifiStatusChanged.emit()
        worker = WifiWorker(mode="connect", ssid=ssid, password=password, parent=self)
        worker.connectFinished.connect(self._on_connect_done)
        self._workers.append(worker)
        worker.start()

    def _on_connect_done(self, ok, message):
        self._wifi_status = message
        self._wifi_busy = False
        self.wifiStatusChanged.emit()
        self.wifiBusyChanged.emit()
        if ok:
            self.scanWifi()

    @pyqtSlot(str, str, str, bool, str, str)
    def finishSetup(self, fullname: str, username: str, password: str, autologin: bool, workspace_style: str, language: str):
        """Validate account inputs and trigger privileged OOBE finalization."""
        if self._apply_busy:
            return

        err = self.validateUsername(username)
        if err:
            self._setup_error = err
            self.setupErrorChanged.emit()
            return
        if len(password) < 4:
            self._setup_error = "Password must be at least 4 characters."
            self.setupErrorChanged.emit()
            return

        self._setup_error = ""
        self._apply_busy = True
        self.setupErrorChanged.emit()
        self.applyBusyChanged.emit()

        payload = {
            "fullname": fullname.strip() or username.strip(),
            "username": username.strip(),
            "password": password,
            "autologin": bool(autologin),
            "workspaceStyle": workspace_style,
            "language": language,
        }
        worker = ApplyWorker(payload, preview_mode=self.preview_mode, parent=self)
        worker.finishedApply.connect(self._on_apply_done)
        self._workers.append(worker)
        worker.start()

    def _on_apply_done(self, ok: bool, message: str):
        self._apply_busy = False
        self.applyBusyChanged.emit()
        if ok:
            self.setupCompleted.emit()
            QTimer.singleShot(1200, QGuiApplication.quit)
        else:
            self._setup_error = message
            self.setupErrorChanged.emit()


def main() -> int:
    preview_mode = "--preview" in sys.argv
    try:
        from PyQt6.QtQuickControls2 import QQuickStyle
        QQuickStyle.setStyle("Basic")
    except Exception:
        pass

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Kushagra OS Setup")
    app.setOrganizationName("Kushagra OS")

    engine = QQmlApplicationEngine()
    backend = OobeBackend(preview_mode=preview_mode)
    resolved = Path(__file__).resolve()
    logo_candidates = [
        Path("/usr/share/kushagra-os/branding/logo-symbol.svg"),
        resolved.parents[1] / "branding" / "logo-symbol.svg",
    ]
    if len(resolved.parents) > 4:
        logo_candidates.append(resolved.parents[4] / "branding" / "logo-symbol.svg")
    logo_candidate = next((p for p in logo_candidates if p.exists()), logo_candidates[1])

    engine.rootContext().setContextProperty("oobeBackend", backend)
    engine.rootContext().setContextProperty("kushagraLogoUrl", QUrl.fromLocalFile(str(logo_candidate)))

    qml_path = Path(__file__).resolve().parent / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
