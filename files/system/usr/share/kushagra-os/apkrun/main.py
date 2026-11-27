#!/usr/bin/env python3
"""Kushagra OS Universal Android (.apk) double-click installer via Waydroid."""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

WAYDROID_CFG = Path("/var/lib/waydroid/waydroid.cfg")
WAYDROID_SERVICE = "waydroid-container.service"
REMOTE_SCHEMES = {
    "smb",
    "mtp",
    "sftp",
    "ftp",
    "fish",
    "trash",
    "http",
    "https",
    "dav",
    "davs",
    "afc",
    "gphoto2",
}


class UnsupportedLocationError(ValueError):
    """Raised when a non-local KIO or remote URI is passed instead of a local path."""


def is_livecd_session() -> bool:
    """Return True when booted into the LiveCD environment (rd.live.image)."""
    try:
        cmdline = Path("/proc/cmdline").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "rd.live.image" in cmdline.split()


def notify_user(title: str, message: str, is_error: bool = False) -> None:
    """Display an informational or error dialog via kdialog, falling back to stdio."""
    if shutil.which("kdialog"):
        flag = "--error" if is_error else "--msgbox"
        subprocess.run(["kdialog", flag, message, "--title", title], check=False)
    else:
        stream = sys.stderr if is_error else sys.stdout
        print(f"{title}: {message}", file=stream)


def confirm_user(title: str, message: str, yes_label: str = "Yes", no_label: str = "Cancel") -> bool:
    """Prompt the user for confirmation via kdialog --yesno."""
    if shutil.which("kdialog"):
        res = subprocess.run(
            [
                "kdialog",
                "--yesno",
                message,
                "--title",
                title,
                "--yes-label",
                yes_label,
                "--no-label",
                no_label,
            ],
            check=False,
        )
        return res.returncode == 0
    print(f"{title}: {message}", file=sys.stderr)
    return False


def resolve_apk_path(raw_arg: str) -> Path:
    """Resolve a local POSIX path or file:// URI while rejecting remote KIO URIs."""
    parsed = urlparse(raw_arg)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc != "localhost":
            raise UnsupportedLocationError(
                f"Remote file URL ({raw_arg}) is not on the local filesystem.\n\n"
                "Please copy the .apk file to a local folder (such as ~/Downloads) first."
            )
        local_path = unquote(parsed.path)
        if not local_path:
            raise UnsupportedLocationError(
                f"Invalid or empty file URL ({raw_arg}).\n\n"
                "Please provide a valid local .apk file path."
            )
        return Path(local_path).resolve()

    if "://" in raw_arg or parsed.scheme in REMOTE_SCHEMES:
        scheme = parsed.scheme or raw_arg.split("://", 1)[0]
        raise UnsupportedLocationError(
            f"Non-local location ({scheme}://) cannot be installed directly.\n\n"
            "Please copy the .apk file to a local folder (such as ~/Downloads) and open it from there."
        )

    return Path(raw_arg).expanduser().resolve()


def validate_apk_file(raw_arg: str) -> Path | None:
    """Validate that raw_arg resolves to a readable local .apk file."""
    try:
        target = resolve_apk_path(raw_arg)
    except UnsupportedLocationError as exc:
        notify_user("Unsupported Location", str(exc), is_error=True)
        return None
    except OSError as exc:
        notify_user("Invalid Path", f"Cannot access file path:\n{raw_arg}\n\n{exc}", is_error=True)
        return None

    if not target.exists():
        notify_user("File Not Found", f"Cannot locate Android package:\n{target}", is_error=True)
        return None

    if not target.is_file():
        notify_user("Invalid Target", f"Expected a regular .apk file:\n{target}", is_error=True)
        return None

    if target.suffix.lower() != ".apk":
        notify_user(
            "Unsupported File Type",
            f"Expected an Android .apk package file:\n{target}",
            is_error=True,
        )
        return None

    if not os.access(target, os.R_OK):
        notify_user(
            "Permission Denied",
            f"Cannot read Android package file:\n{target}",
            is_error=True,
        )
        return None

    return target


def offer_waydroid_setup() -> int:
    """Explain Waydroid initialization and optionally launch Konsole with ujust setup-waydroid."""
    message = (
        "Waydroid Android subsystem is not initialized yet.\n\n"
        "Run 'ujust setup-waydroid' once to initialize Waydroid, configure firewall rules, "
        "and install CPU-matched ARM translation (libhoudini / libndk).\n\n"
        "Compatibility Note: Indian UPI and banking apps (GPay, PhonePe, Paytm, DigiLocker) "
        "require Google Play Integrity (MEETS_STRONG_INTEGRITY) and will NOT work in Waydroid.\n\n"
        "Open Konsole now to run 'ujust setup-waydroid'?"
    )
    if shutil.which("konsole"):
        if confirm_user(
            "Waydroid Setup Required",
            message,
            yes_label="Open Konsole & Setup",
            no_label="Cancel",
        ):
            subprocess.Popen(
                [
                    "konsole",
                    "-e",
                    "bash",
                    "-c",
                    "ujust setup-waydroid; echo ''; read -rp 'Press Enter to close...' _",
                ],
                start_new_session=True,
            )
            return 0
        return 1

    notify_user(
        "Waydroid Setup Required",
        "Waydroid Android subsystem is not initialized yet.\n\n"
        "Open a terminal and run:\n  ujust setup-waydroid",
        is_error=True,
    )
    return 1


def is_container_active() -> bool:
    """Return True if waydroid-container.service is active."""
    res = subprocess.run(
        ["systemctl", "is-active", "--quiet", WAYDROID_SERVICE],
        check=False,
    )
    return res.returncode == 0


def ensure_container_running() -> bool:
    """Check waydroid-container.service and prompt to start it via pkexec if stopped."""
    if is_container_active():
        return True

    if not confirm_user(
        "Start Waydroid Container?",
        f"The Waydroid background service ({WAYDROID_SERVICE}) is currently stopped.\n\n"
        "Start it now so your .apk package can be installed?",
        yes_label="Start Waydroid Service",
        no_label="Cancel",
    ):
        return False

    res = subprocess.run(
        ["pkexec", "systemctl", "start", WAYDROID_SERVICE],
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or f"pkexec exited with status {res.returncode}").strip()
        notify_user(
            "Failed to Start Waydroid Service",
            f"Could not start {WAYDROID_SERVICE}.\n\n{detail}",
            is_error=True,
        )
        return False

    for _ in range(6):
        if is_container_active():
            return True
        time.sleep(0.5)

    notify_user(
        "Waydroid Service Inactive",
        f"{WAYDROID_SERVICE} did not become active in time.",
        is_error=True,
    )
    return False


def is_waydroid_session_running() -> bool:
    """Parse `waydroid status` and return True when Session reports RUNNING."""
    try:
        res = subprocess.run(
            ["waydroid", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    for line in res.stdout.splitlines():
        if line.strip().startswith("Session:"):
            state = line.split(":", 1)[1].strip().upper()
            return state == "RUNNING"
    return False


def ensure_session_running() -> bool:
    """Ensure the user's Waydroid Android session is active, starting it in background if needed."""
    if is_waydroid_session_running():
        return True

    try:
        proc = subprocess.Popen(
            ["waydroid", "session", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        notify_user(
            "Waydroid Session Error",
            f"Failed to start Waydroid session:\n{exc}",
            is_error=True,
        )
        return False

    for _ in range(20):
        time.sleep(1.0)
        if is_waydroid_session_running():
            return True
        if proc.poll() is not None and proc.returncode != 0:
            # Re-check once before failing in case session daemonized cleanly
            time.sleep(0.5)
            if is_waydroid_session_running():
                return True
            notify_user(
                "Waydroid Session Failed",
                f"'waydroid session start' exited with status {proc.returncode}.\n\n"
                "Run 'waydroid session start' in Konsole to inspect details.",
                is_error=True,
            )
            return False

    notify_user(
        "Waydroid Session Timeout",
        "Waydroid session did not become ready in time.\n\n"
        "Try running 'waydroid session start' in Konsole and check 'waydroid status'.",
        is_error=True,
    )
    return False


def install_apk(target: Path) -> int:
    """Confirm APK installation with Play Integrity notice and run `waydroid app install`."""
    confirmed = confirm_user(
        "Install Android App (.apk)",
        f"Install Android package into Waydroid?\n\n"
        f"Package: {target.name}\n"
        f"Location: {target}\n\n"
        "Important Compatibility Notice:\n"
        "• Waydroid cannot pass hardware Google Play Integrity (MEETS_STRONG_INTEGRITY).\n"
        "• Indian UPI and banking apps (GPay, PhonePe, Paytm, DigiLocker) will NOT work reliably.\n"
        "• Only install .apk files from sources you trust.",
        yes_label="Install APK",
        no_label="Cancel",
    )
    if not confirmed:
        return 0

    try:
        res = subprocess.run(
            ["waydroid", "app", "install", str(target)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        notify_user(
            "APK Installation Timed Out",
            f"Installing {target.name} took too long and timed out.",
            is_error=True,
        )
        return 1
    except OSError as exc:
        notify_user(
            "APK Installation Failed",
            f"Could not execute waydroid:\n{exc}",
            is_error=True,
        )
        return 1

    if res.returncode == 0:
        notify_user(
            "Android App Installed",
            f"Successfully installed:\n{target.name}\n\n"
            "You can now launch the app from the Application Launcher or Waydroid.",
        )
        return 0

    detail = (res.stderr or res.stdout or f"waydroid app install exited with status {res.returncode}").strip()
    notify_user(
        "APK Installation Failed",
        f"Could not install {target.name} in Waydroid.\n\n{detail}",
        is_error=True,
    )
    return 1


def main() -> int:
    if is_livecd_session():
        notify_user(
            "Waydroid Blocked in LiveCD",
            "Waydroid Android apps cannot be installed or run inside a LiveCD USB session.\n\n"
            "Install Kushagra OS to disk first, then run 'ujust setup-waydroid'.",
            is_error=True,
        )
        return 1

    if len(sys.argv) < 2 or not sys.argv[1].strip():
        notify_user("Kushagra Android APK Installer", "Usage: kushagra-apkrun <path-to-app.apk>")
        return 1

    target = validate_apk_file(sys.argv[1])
    if target is None:
        return 1

    if not shutil.which("waydroid"):
        notify_user(
            "Waydroid Not Found",
            "The 'waydroid' runtime was not found on this system.",
            is_error=True,
        )
        return 1

    if not WAYDROID_CFG.is_file():
        return offer_waydroid_setup()

    if not ensure_container_running():
        return 1

    if not ensure_session_running():
        return 1

    return install_apk(target)


if __name__ == "__main__":
    sys.exit(main())
