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


def notify_user(title: str, message: str, is_error: bool = False) -> None:
    if shutil.which("kdialog"):
        flag = "--error" if is_error else "--msgbox"
        subprocess.run(["kdialog", flag, message, "--title", title], check=False)
    else:
        stream = sys.stderr if is_error else sys.stdout
        print(f"{title}: {message}", file=stream)


def resolve_target_path(raw_arg: str) -> Path:
    if raw_arg.startswith("file://"):
        parsed = urlparse(raw_arg)
        return Path(unquote(parsed.path)).resolve()
    return Path(raw_arg).expanduser().resolve()


def bottles_flatpak_installed() -> bool:
    if not shutil.which("flatpak"):
        return False
    res = subprocess.run(["flatpak", "info", BOTTLES_APP_ID], capture_output=True, text=True, check=False)
    return res.returncode == 0


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
    bottle_dir = bottles_data / "bottles" / DEFAULT_BOTTLE

    has_runner = runners_dir.exists() and any(runners_dir.iterdir())
    if has_runner and bottle_dir.exists():
        cli_cmd = [
            "flatpak", "run",
            f"--filesystem={parent_dir}",
            "--command=bottles-cli",
            BOTTLES_APP_ID,
            "run",
            "-b", DEFAULT_BOTTLE,
        ]
        if is_msi:
            cli_cmd.extend(["-e", "msiexec", "--args", f'/i "{target}"'])
        else:
            cli_cmd.extend(["-e", str(target)])
        res = subprocess.call(cli_cmd)
        if res == 0:
            return 0

    return subprocess.call([
        "flatpak", "run",
        f"--filesystem={parent_dir}",
        BOTTLES_APP_ID,
        str(target),
    ])


def main() -> int:
    if len(sys.argv) < 2:
        notify_user("Kushagra Windows App Runner", "Usage: kushagra-winrun <path-to-installer.exe|msi>")
        return 1

    target = resolve_target_path(sys.argv[1])
    if not target.exists():
        notify_user("File Not Found", f"Cannot locate Windows file:\n{target}", is_error=True)
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
