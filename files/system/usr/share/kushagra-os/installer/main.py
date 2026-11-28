#!/usr/bin/env python3
"""Kushagra OS Stage 1 K-Installer Qt6/QML Application."""

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QEventLoop, QObject, QSize, QThread, QTimer, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication, QWindow
from PyQt6.QtQml import QQmlApplicationEngine

sys.path.insert(0, "/usr/share/kushagra-os/installer")
import storage_probe

LEGACY_RAM_THRESHOLD_KIB = 7549747  # ~7.2 GiB (under 8 GB RAM baseline)


def _detect_ram_info(meminfo_path: str = "/proc/meminfo") -> tuple[float, bool]:
    """Read /proc/meminfo MemTotal and return (ram_gib, legacy_ram_advisory)."""
    try:
        text = Path(meminfo_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0.0, False
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE | re.IGNORECASE)
    if not match:
        return 0.0, False
    mem_kib = int(match.group(1))
    ram_gib = round((mem_kib * 1024.0) / (1024 ** 3), 2)
    return ram_gib, (mem_kib < LEGACY_RAM_THRESHOLD_KIB)


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
                err_detail = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
                data = storage_probe.scan_storage(allow_privileged=False)
                prev_err = data.get("error", "").strip()
                msg = f"Privileged storage scan failed (code {res.returncode}): {err_detail}"
                data["error"] = f"{msg} | {prev_err}" if prev_err else msg
                self.scanFinished.emit(data)
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
                (12, "Preview: Verifying offline OCI payload & EFI partition...", ["Dry-run: /run/initramfs/live/kushagra-oci validated."]),
                (25, "Preview: Creating Btrfs sysroot & var/home subvolume...", ["Dry-run: subvolid=5,compress=zstd:1 & var/home ready."]),
                (68, "Preview: Deploying offline Kushagra OS bootc image...", ["Dry-run: bootc install to-filesystem simulation..."]),
                (90, "Preview: Writing update-safe GRUB2 custom.cfg & arming Stage 2 OOBE...", ["Dry-run: kushagra-dualboot-grub custom.cfg & /var/lib/kushagra-oobe-pending staged."]),
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


def _find_plasma_probe_cmd():
    """Locate Qt6 qdbus or gdbus binary to probe org.kde.plasmashell /PlasmaShell."""
    for candidate in ("qdbus-qt6", "/usr/lib64/qt6/bin/qdbus", "qdbus6", "qdbus"):
        resolved = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if resolved and os.access(resolved, os.X_OK):
            return [resolved, "org.kde.plasmashell", "/PlasmaShell"], False
    gdbus_bin = shutil.which("gdbus")
    if gdbus_bin:
        return [
            gdbus_bin,
            "introspect",
            "--session",
            "--dest",
            "org.kde.plasmashell",
            "--object-path",
            "/PlasmaShell",
        ], True
    return None, False


class RestoreDesktopWorker(QThread):
    """Non-blocking LiveCD Plasma shell restoration before exiting K-Installer."""

    finishedRestore = pyqtSignal(bool)

    def __init__(self, launch_anaconda: bool = False, parent=None):
        super().__init__(parent)
        self.launch_anaconda = launch_anaconda

    def run(self):
        config_dir = Path.home() / ".config"

        for mask_rel in (
            Path("systemd") / "user" / "plasma-plasmashell.service",
            Path("systemd") / "user" / "plasma-wallpaper.service",
        ):
            mask_path = config_dir / mask_rel
            try:
                if os.path.lexists(mask_path) and (
                    (mask_path.is_symlink() and (os.readlink(mask_path) == "/dev/null" or os.path.realpath(mask_path) == "/dev/null"))
                    or (mask_path.is_file() and mask_path.stat().st_size == 0)
                ):
                    mask_path.unlink()
            except Exception:
                pass

        autostart_plasma = config_dir / "autostart" / "org.kde.plasmashell.desktop"
        try:
            if os.path.lexists(autostart_plasma) and (
                autostart_plasma.is_symlink()
                or "hidden=true" in autostart_plasma.read_text(encoding="utf-8", errors="ignore").lower()
            ):
                autostart_plasma.unlink()
        except Exception:
            pass

        if shutil.which("systemctl"):
            try:
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=6,
                )
            except Exception:
                pass

            for unit in ("plasma-wallpaper.service", "plasma-plasmashell.service"):
                try:
                    subprocess.run(
                        ["systemctl", "--user", "start", unit],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                        timeout=8,
                    )
                except Exception:
                    pass

        probe_cmd, use_gdbus = _find_plasma_probe_cmd()
        if probe_cmd:
            for _ in range(24):  # Poll up to 6s (0.25s step) so shell & panel render before exit
                try:
                    res = subprocess.run(
                        probe_cmd,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=2,
                    )
                    if res.returncode == 0 and (not use_gdbus or "org.kde.PlasmaShell" in res.stdout):
                        break
                except Exception:
                    pass
                time.sleep(0.25)

        self.finishedRestore.emit(self.launch_anaconda)


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
    launchingDesktopChanged = pyqtSignal()
    ramGibChanged = pyqtSignal()
    legacyRamAdvisoryChanged = pyqtSignal()

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
        self._launching_desktop = False
        self._ram_gib, self._legacy_ram_advisory = _detect_ram_info()
        self._restore_worker = None
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

    @pyqtProperty(bool, notify=launchingDesktopChanged)
    def launchingDesktop(self):
        return self._launching_desktop

    @pyqtProperty(float, notify=ramGibChanged)
    def ramGib(self):
        return self._ram_gib

    @pyqtProperty(bool, notify=legacyRamAdvisoryChanged)
    def legacyRamAdvisory(self):
        return self._legacy_ram_advisory

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

    def _restore_live_desktop(self, launch_anaconda: bool = False):
        if self._launching_desktop or self._installing:
            return
        self._launching_desktop = True
        self.launchingDesktopChanged.emit()

        worker = RestoreDesktopWorker(launch_anaconda=launch_anaconda, parent=self)
        worker.finishedRestore.connect(self._on_restore_finished)
        self._restore_worker = worker
        self._workers.append(worker)
        worker.start()

    def _on_restore_finished(self, launch_anaconda: bool):
        if self._restore_worker is not None:
            self._restore_worker.wait(1000)
        if launch_anaconda:
            try:
                subprocess.Popen(["liveinst"], start_new_session=True)
            except Exception:
                pass
        QGuiApplication.quit()

    @pyqtSlot()
    def tryLiveDesktop(self):
        if self.preview_mode:
            QGuiApplication.quit()
            return
        self._restore_live_desktop(launch_anaconda=False)

    @pyqtSlot()
    def launchClassicAnaconda(self):
        if self.preview_mode:
            QGuiApplication.quit()
            return
        self._restore_live_desktop(launch_anaconda=True)

    @pyqtSlot()
    def rebootNow(self):
        if self.preview_mode:
            QGuiApplication.quit()
            return
        subprocess.run(["systemctl", "reboot"], check=False)


def _is_real_screen(s) -> bool:
    """Return True only when QScreen represents a real non-placeholder output."""
    return (
        s is not None
        and bool(s.name().strip())
        and s.geometry().width() > 0
        and s.geometry().height() > 0
    )


def _wait_for_real_screen(app: QGuiApplication, timeout_ms: int = 1500) -> None:
    """Wait briefly for kscreen/Wayland output initialization before mapping."""
    if any(_is_real_screen(s) for s in app.screens()):
        return

    loop = QEventLoop()
    waiting = {"active": True}
    seen_placeholders = set()
    placeholder_conns = []

    def _check_ready(screen=None):
        if not waiting["active"]:
            return
        if _is_real_screen(screen) or any(_is_real_screen(s) for s in app.screens()):
            waiting["active"] = False
            loop.quit()
        elif screen is not None:
            _watch_placeholder(screen)

    def _watch_placeholder(sc):
        if sc is None or id(sc) in seen_placeholders:
            return
        seen_placeholders.add(id(sc))

        def _on_geo(_geo, s=sc):
            _check_ready(s)

        sc.geometryChanged.connect(_on_geo)
        placeholder_conns.append((sc, _on_geo))

    app.screenAdded.connect(_check_ready)
    for existing in app.screens():
        _watch_placeholder(existing)

    QTimer.singleShot(timeout_ms, loop.quit)
    loop.exec()
    waiting["active"] = False
    try:
        app.screenAdded.disconnect(_check_ready)
    except Exception:
        pass
    for sc, slot in placeholder_conns:
        try:
            sc.geometryChanged.disconnect(slot)
        except Exception:
            pass


def _bind_fullscreen_sync(app: QGuiApplication, win: QWindow) -> None:
    """Bind screen/output listeners and synchronize fullscreen geometry on Wayland."""
    state = {"busy": False}
    connected_screens = set()

    def _pick_target():
        for screen in app.screens():
            if _is_real_screen(screen):
                return screen
        return app.primaryScreen()

    def _attach_screen(s):
        if s is None or id(s) in connected_screens:
            return
        connected_screens.add(id(s))
        s.geometryChanged.connect(sync_fullscreen)
        s.virtualGeometryChanged.connect(sync_fullscreen)
        s.physicalDotsPerInchChanged.connect(sync_fullscreen)

    def sync_fullscreen(*_args):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            target = _pick_target()
            if target is None:
                if not win.isVisible():
                    win.showFullScreen()
                return

            _attach_screen(target)
            target_geo = target.geometry()
            has_valid_geo = target_geo.width() > 0 and target_geo.height() > 0

            needs_sync = (
                not win.isVisible()
                or win.visibility() != QWindow.Visibility.FullScreen
                or (has_valid_geo and win.geometry() != target_geo)
                or win.screen() != target
            )
            if not needs_sync:
                return

            win.setMinimumSize(QSize(0, 0))
            win.setScreen(target)
            if has_valid_geo:
                win.setGeometry(target_geo)
            if not win.isVisible() or win.visibility() != QWindow.Visibility.FullScreen:
                win.showFullScreen()
        finally:
            state["busy"] = False

    def _on_screen_event(screen=None):
        _attach_screen(screen)
        sync_fullscreen()

    for screen in app.screens():
        _attach_screen(screen)
    _attach_screen(app.primaryScreen())

    app.screenAdded.connect(_on_screen_event)
    app.screenRemoved.connect(sync_fullscreen)
    app.primaryScreenChanged.connect(_on_screen_event)
    win.screenChanged.connect(_on_screen_event)

    sync_fullscreen()
    QTimer.singleShot(500, sync_fullscreen)
    QTimer.singleShot(1500, sync_fullscreen)
    QTimer.singleShot(3000, sync_fullscreen)


def main() -> int:
    preview_mode = "--preview" in sys.argv
    app = QGuiApplication(sys.argv)
    app.setApplicationName("Kushagra OS Installer")
    app.setOrganizationName("Kushagra OS")

    try:
        from PyQt6.QtQuickControls2 import QQuickStyle
        QQuickStyle.setStyle("Basic")
    except Exception:
        pass

    engine = QQmlApplicationEngine()
    backend = InstallerBackend(preview_mode=preview_mode, parent=engine)

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

    win = engine.rootObjects()[0]
    _wait_for_real_screen(app, timeout_ms=1500)
    if isinstance(win, QWindow):
        _bind_fullscreen_sync(app, win)
    elif hasattr(win, "showFullScreen"):
        win.showFullScreen()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
