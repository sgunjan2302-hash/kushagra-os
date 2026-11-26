#!/usr/bin/env python3
"""Kushagra OS Stage 1 K-Installer Qt6/QML Application."""

import json
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

sys.path.insert(0, "/usr/share/kushagra-os/installer")
import storage_probe


class ScanWorker(QThread):
    """Non-blocking storage scanner running via scoped Polkit backend."""

    scanFinished = pyqtSignal(dict)

    def __init__(self, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.preview_mode = preview_mode

    def run(self):
        if self.preview_mode:
            self.scanFinished.emit(storage_probe.preview_sample_storage())
            return

        helper = "/usr/libexec/kushagra-installer-backend"
        if os.path.exists(helper):
            try:
                cmd = [helper, "--scan"] if os.geteuid() == 0 else ["pkexec", helper, "--scan"]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
                if res.returncode == 0 and res.stdout.strip():
                    self.scanFinished.emit(json.loads(res.stdout))
                    return
            except Exception as exc:
                data = storage_probe.scan_storage(allow_privileged=False)
                data["error"] = f"Privileged probe fallback ({exc})"
                self.scanFinished.emit(data)
                return

        self.scanFinished.emit(storage_probe.scan_storage(allow_privileged=False))


class InstallWorker(QThread):
    """Non-blocking installation worker streaming PROGRESS lines from backend."""

    progressUpdated = pyqtSignal(int, str, list)
    finishedInstall = pyqtSignal(bool, str)

    def __init__(self, target_id: str, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.target_id = target_id
        self.preview_mode = preview_mode

    def run(self):
        if self.preview_mode:
            steps = [
                (15, "Preview: Initializing storage & checking EFI partition...", ["Dry-run: clearpart --none validated."]),
                (35, "Preview: Creating Btrfs subvolumes (root, var, home)...", ["Dry-run: subvol setup ready."]),
                (70, "Preview: Deploying Kushagra OS immutable image...", ["Dry-run: LiveOS copy simulation..."]),
                (90, "Preview: Updating UEFI GRUB2 & arming Stage 2 OOBE...", ["Dry-run: /var/lib/kushagra-oobe-pending staged."]),
                (100, "Preview complete (no disk writes performed).", ["Preview mode succeeded cleanly."]),
            ]
            for pct, stage, logs in steps:
                self.progressUpdated.emit(pct, stage, logs)
                self.msleep(650)
            self.finishedInstall.emit(True, "Preview mode finished safely.")
            return

        helper = "/usr/libexec/kushagra-installer-backend"
        if not os.path.exists(helper):
            self.finishedInstall.emit(False, f"Missing installer helper: {helper}")
            return

        cmd = [helper, "--install"] if os.geteuid() == 0 else ["pkexec", helper, "--install"]
        payload = json.dumps({"targetId": self.target_id, "confirmed": True})

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            proc.stdin.write(payload)
            proc.stdin.close()

            last_lines = []
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("PROGRESS "):
                    try:
                        evt = json.loads(line[9:])
                        logs = evt.get("logs", [])
                        last_lines.extend(logs)
                        last_lines = last_lines[-120:]
                        self.progressUpdated.emit(
                            int(evt.get("percent", 0)),
                            str(evt.get("stage", "")),
                            logs,
                        )
                    except Exception:
                        pass
                else:
                    last_lines.append(line)
                    last_lines = last_lines[-120:]
                    self.progressUpdated.emit(-1, "", [line])

            ret = proc.wait()
            if ret == 0:
                self.finishedInstall.emit(True, "Installation completed cleanly.")
            else:
                tail = last_lines[-1] if last_lines else f"exit code {ret}"
                self.finishedInstall.emit(False, f"Installation failed (code {ret}): {tail}")
        except Exception as exc:
            self.finishedInstall.emit(False, f"Installer process error: {exc}")


class InstallerBackend(QObject):
    """Qt6/QML bridge for Kushagra OS K-Installer."""

    disksChanged = pyqtSignal()
    scanningChanged = pyqtSignal()
    scanErrorChanged = pyqtSignal()
    recommendedTargetIdChanged = pyqtSignal()
    installingChanged = pyqtSignal()
    installPercentChanged = pyqtSignal()
    installStageChanged = pyqtSignal()
    installLogsChanged = pyqtSignal()
    installErrorChanged = pyqtSignal()
    installSucceededChanged = pyqtSignal()

    def __init__(self, preview_mode: bool = False, parent=None):
        super().__init__(parent)
        self.preview_mode = preview_mode
        self._disks = []
        self._scanning = False
        self._scan_error = ""
        self._recommended_target_id = ""
        self._installing = False
        self._install_percent = 0
        self._install_stage = ""
        self._install_logs = []
        self._install_error = ""
        self._install_succeeded = False
        self._workers = []

    @pyqtProperty(list, notify=disksChanged)
    def disks(self):
        return self._disks

    @pyqtProperty(bool, notify=scanningChanged)
    def scanning(self):
        return self._scanning

    @pyqtProperty(str, notify=scanErrorChanged)
    def scanError(self):
        return self._scan_error

    @pyqtProperty(str, notify=recommendedTargetIdChanged)
    def recommendedTargetId(self):
        return self._recommended_target_id

    @pyqtProperty(bool, notify=installingChanged)
    def installing(self):
        return self._installing

    @pyqtProperty(int, notify=installPercentChanged)
    def installPercent(self):
        return self._install_percent

    @pyqtProperty(str, notify=installStageChanged)
    def installStage(self):
        return self._install_stage

    @pyqtProperty(str, notify=installLogsChanged)
    def installLogsText(self):
        return "\n".join(self._install_logs[-200:])

    @pyqtProperty(str, notify=installErrorChanged)
    def installError(self):
        return self._install_error

    @pyqtProperty(bool, notify=installSucceededChanged)
    def installSucceeded(self):
        return self._install_succeeded

    @pyqtSlot()
    def scanDrives(self):
        if self._scanning:
            return
        self._scanning = True
        self._scan_error = ""
        self.scanningChanged.emit()
        self.scanErrorChanged.emit()

        worker = ScanWorker(preview_mode=self.preview_mode, parent=self)
        worker.scanFinished.connect(self._on_scan_finished)
        self._workers.append(worker)
        worker.start()

    def _on_scan_finished(self, result: dict):
        self._scanning = False
        self._disks = result.get("disks", [])
        self._scan_error = result.get("error", "")
        self._recommended_target_id = result.get("recommendedTargetId", "")
        self.disksChanged.emit()
        self.scanErrorChanged.emit()
        self.recommendedTargetIdChanged.emit()
        self.scanningChanged.emit()

    @pyqtSlot(str)
    def startInstall(self, target_id: str):
        if self._installing or not target_id:
            return
        self._installing = True
        self._install_succeeded = False
        self._install_error = ""
        self._install_percent = 3
        self._install_stage = "Starting Kushagra OS installation..."
        self._install_logs = []
        self.installingChanged.emit()
        self.installSucceededChanged.emit()
        self.installErrorChanged.emit()
        self.installPercentChanged.emit()
        self.installStageChanged.emit()
        self.installLogsChanged.emit()

        worker = InstallWorker(target_id, preview_mode=self.preview_mode, parent=self)
        worker.progressUpdated.connect(self._on_progress_updated)
        worker.finishedInstall.connect(self._on_install_finished)
        self._workers.append(worker)
        worker.start()

    def _on_progress_updated(self, percent: int, stage: str, new_lines: list):
        if percent >= 0 and percent != self._install_percent:
            self._install_percent = percent
            self.installPercentChanged.emit()
        if stage and stage != self._install_stage:
            self._install_stage = stage
            self.installStageChanged.emit()
        if new_lines:
            self._install_logs.extend(new_lines)
            self._install_logs = self._install_logs[-250:]
            self.installLogsChanged.emit()

    def _on_install_finished(self, ok: bool, message: str):
        self._installing = False
        self.installingChanged.emit()
        if ok:
            self._install_percent = 100
            self._install_stage = "Installation complete!"
            self._install_succeeded = True
            self.installPercentChanged.emit()
            self.installStageChanged.emit()
            self.installSucceededChanged.emit()
        else:
            self._install_error = message
            self.installErrorChanged.emit()

    @pyqtSlot()
    def tryLiveDesktop(self):
        QGuiApplication.quit()

    @pyqtSlot()
    def launchClassicAnaconda(self):
        if self.preview_mode:
            QGuiApplication.quit()
            return
        subprocess.Popen(["liveinst"], start_new_session=True)
        QGuiApplication.quit()

    @pyqtSlot()
    def rebootNow(self):
        if self.preview_mode:
            QGuiApplication.quit()
            return
        subprocess.run(["systemctl", "reboot"], check=False)


def main() -> int:
    preview_mode = "--preview" in sys.argv
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Kushagra OS Installer")
    app.setOrganizationName("Kushagra OS")

    backend = InstallerBackend(preview_mode=preview_mode)
    engine = QQmlApplicationEngine()

    base_dir = Path(__file__).resolve().parent
    logo_path = Path("/usr/share/kushagra-os/branding/logo-symbol.svg")
    if not logo_path.exists():
        logo_path = base_dir.parent / "branding" / "logo-symbol.svg"

    ctx = engine.rootContext()
    ctx.setContextProperty("installerBackend", backend)
    ctx.setContextProperty("kushagraLogoUrl", QUrl.fromLocalFile(str(logo_path)))
    ctx.setContextProperty("isPreviewMode", preview_mode)

    qml_path = base_dir / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
