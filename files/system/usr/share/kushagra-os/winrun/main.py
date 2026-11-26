#!/usr/bin/env python3
"""Kushagra OS Windows (.exe / .msi) double-click compatibility launcher."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BOTTLES_APP_ID = "com.usebottles.bottles"
DEFAULT_BOTTLE = "KushagraApps"


class UnsupportedLocationError(ValueError):
    """Raised when a non-local KIO or remote URI is passed instead of a local path."""


def notify_user(title: str, message: str, is_error: bool = False) -> None:
    if shutil.which("kdialog"):
        flag = "--error" if is_error else "--msgbox"
        subprocess.run(["kdialog", flag, message, "--title", title], check=False)
    else:
        stream = sys.stderr if is_error else sys.stdout
        print(f"{title}: {message}", file=stream)


def resolve_target_path(raw_arg: str) -> Path:
    parsed = urlparse(raw_arg)
    if parsed.scheme == "file":
        if parsed.netloc and parsed.netloc != "localhost":
            raise UnsupportedLocationError(
                f"Remote file URL ({raw_arg}) is not on the local filesystem.\n\n"
                "Please copy the .exe or .msi file to a local folder (such as ~/Downloads) first."
            )
        local_path = unquote(parsed.path)
        if not local_path:
            raise UnsupportedLocationError(
                f"Invalid or empty file URL ({raw_arg}).\n\n"
                "Please provide a valid local .exe or .msi file path."
            )
        return Path(local_path).resolve()

    if "://" in raw_arg or parsed.scheme in {"smb", "mtp", "sftp", "ftp", "fish", "trash"}:
        scheme = parsed.scheme or raw_arg.split("://", 1)[0]
        raise UnsupportedLocationError(
            f"Non-local location ({scheme}://) cannot be launched directly.\n\n"
            "Please copy the .exe or .msi file to a local folder (such as ~/Downloads) and open it from there."
        )

    return Path(raw_arg).expanduser().resolve()


def bottles_flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    res = subprocess.run(["flatpak", "info", BOTTLES_APP_ID], capture_output=True, text=True, check=False)
    return res.returncode == 0


def find_existing_bottle(bottles_dir: Path) -> str | None:
    if not bottles_dir.is_dir():
        return None
    preferred = bottles_dir / DEFAULT_BOTTLE
    if preferred.is_dir() and (preferred / "bottle.yml").is_file():
        return DEFAULT_BOTTLE
    for entry in sorted(bottles_dir.iterdir(), key=lambda p: p.name.lower()):
        if entry.is_dir() and not entry.name.startswith(".") and (entry / "bottle.yml").is_file():
            return entry.name
    return None


def launch_with_umu(target: Path, is_msi: bool) -> int:
    prefix = Path.home() / ".local" / "share" / "kushagra-winapps"
    prefix.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.setdefault("WINEPREFIX", str(prefix))
    env.setdefault("GAMEID", "umu-default")

    cmd = ["umu-run", "msiexec", "/i", str(target)] if is_msi else ["umu-run", str(target)]
    return subprocess.call(cmd, env=env)


def launch_with_bottles(target: Path, is_msi: bool) -> int:
    parent_dir = str(target.parent)
    bottles_data = Path.home() / ".var" / "app" / BOTTLES_APP_ID / "data" / "bottles"
    runners_dir = bottles_data / "runners"
    bottles_dir = bottles_data / "bottles"

    has_runner = runners_dir.is_dir() and any(
        not entry.name.startswith(".") for entry in runners_dir.iterdir()
    )
    bottle_name = find_existing_bottle(bottles_dir)

    if has_runner and bottle_name:
        cli_cmd = [
            "flatpak", "run",
            f"--filesystem={parent_dir}",
            "--command=bottles-cli",
            BOTTLES_APP_ID,
            "run",
            "-b", bottle_name,
        ]
        if is_msi:
            cli_cmd.extend(["-e", "msiexec", "--args", f'/i "{target}"'])
        else:
            cli_cmd.extend(["-e", str(target)])
        res = subprocess.call(cli_cmd)
        if res == 0:
            return 0
    else:
        notify_user(
            "Bottles Setup Required",
            "No configured Windows bottle was found yet.\n\n"
            "Bottles will now open so you can finish initial setup and create a bottle, "
            f"then choose 'Run Executable...' and select:\n{target}",
        )

    return subprocess.call([
        "flatpak", "run",
        f"--filesystem={parent_dir}",
        BOTTLES_APP_ID,
    ])


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        notify_user("Kushagra Windows App Runner", "Usage: kushagra-winrun <path-to-installer.exe|msi>")
        return 1

    try:
        target = resolve_target_path(sys.argv[1])
    except UnsupportedLocationError as exc:
        notify_user("Unsupported Location", str(exc), is_error=True)
        return 1

    if not target.exists():
        notify_user("File Not Found", f"Cannot locate Windows file:\n{target}", is_error=True)
        return 1

    if not target.is_file():
        notify_user("Invalid Target", f"Expected a Windows .exe or .msi file:\n{target}", is_error=True)
        return 1

    is_msi = target.suffix.lower() == ".msi"

    if shutil.which("umu-run"):
        return launch_with_umu(target, is_msi)

    if bottles_flatpak_installed():
        return launch_with_bottles(target, is_msi)

    if shutil.which("wine"):
        cmd = ["wine", "msiexec", "/i", str(target)] if is_msi else ["wine", str(target)]
        return subprocess.call(cmd)

    notify_user(
        "Windows Runtime Setup Pending",
        "Bottles (com.usebottles.bottles) is still finishing background Flatpak setup or is not installed yet.\n\n"
        "Wait a moment for background Flatpak setup, or open Bazaar Store to install Bottles.",
        is_error=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
