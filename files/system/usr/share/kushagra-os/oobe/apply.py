#!/usr/bin/env python3
"""Privileged system-apply helper for Kushagra OS OOBE (runs via pkexec)."""

import json
import os
import pwd
import re
import shutil
import subprocess
import sys

OOBE_FLAG = "/var/lib/kushagra-oobe-pending"
OOBE_DONE = "/etc/kushagra-oobe-done"
OOBE_AUTOLOGIN_CONF = "/etc/plasmalogin.conf.d/00-kushagra-oobe.conf"
USER_AUTOLOGIN_CONF = "/etc/plasmalogin.conf.d/10-user-autologin.conf"
USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
RESERVED_USERS = {"root", "liveuser", "kushagra-oobe", "plasma-setup", "nobody"}


def run_checked(cmd, input_text=None):
    """Run subprocess without shell interpolation and raise descriptive error on failure."""
    res = subprocess.run(cmd, input=input_text, text=True, capture_output=True)
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or f"exit {res.returncode}").strip()
        raise RuntimeError(f"Command {' '.join(cmd)} failed: {detail}")
    return res


def configure_fcitx5(home_dir: str, language: str) -> None:
    """Provision Fcitx5 Wayland input method profile with Hindi m17n support."""
    fcitx_dir = os.path.join(home_dir, ".config", "fcitx5")
    os.makedirs(fcitx_dir, exist_ok=True)

    # Set verified m17n Hindi layouts alongside Indian English keyboard
    if language == "hi_IN":
        items = ["keyboard-in-eng", "m17n_hi_itrans", "m17n_hi_inscript2"]
    else:
        items = ["keyboard-in-eng", "m17n_hi_itrans"]

    lines = [
        "[Groups/0]",
        "Name=Default",
        f"Default Layout=in-eng",
        f"DefaultIM={items[0]}",
        "",
    ]
    for idx, im_name in enumerate(items):
        lines.extend([
            f"[Groups/0/Items/{idx}]",
            f"Name={im_name}",
            "Layout=",
            "",
        ])
    lines.extend(["[GroupOrder]", "0=Default", ""])

    with open(os.path.join(fcitx_dir, "profile"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines))


def stage_workspace_hook(home_dir: str, workspace_style: str) -> None:
    """Install one-shot autostart script to apply the chosen KDE Plasma 6 layout."""
    style = "floating" if workspace_style == "floating" else "classic"
    autostart_dir = os.path.join(home_dir, ".config", "autostart")
    os.makedirs(autostart_dir, exist_ok=True)
    desktop_path = os.path.join(autostart_dir, "kushagra-firstboot-layout.desktop")
    content = "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=Kushagra OS Apply Initial Layout",
        f"Exec=/usr/libexec/kushagra-apply-user-layout {style}",
        "NoDisplay=true",
        "X-KDE-autostart-phase=2",
        "",
    ])
    with open(desktop_path, "w", encoding="utf-8") as fp:
        fp.write(content)


def configure_plasmalogin(username: str, autologin: bool) -> None:
    """Remove OOBE autologin and configure normal user autologin or password login."""
    conf_dir = "/etc/plasmalogin.conf.d"
    os.makedirs(conf_dir, exist_ok=True)
    os.chmod(conf_dir, 0o755)
    if os.path.exists(OOBE_AUTOLOGIN_CONF):
        os.remove(OOBE_AUTOLOGIN_CONF)

    if autologin:
        with open(USER_AUTOLOGIN_CONF, "w", encoding="utf-8") as fp:
            fp.write(f"[Autologin]\nUser={username}\nSession=plasma.desktop\nRelogin=false\n")
        os.chmod(USER_AUTOLOGIN_CONF, 0o644)
    elif os.path.exists(USER_AUTOLOGIN_CONF):
        os.remove(USER_AUTOLOGIN_CONF)

    if shutil.which("restorecon"):
        subprocess.run(["restorecon", "-RF", conf_dir], check=False)


def main() -> int:
    if os.geteuid() != 0:
        print("Error: kushagra-oobe-apply must run as root via pkexec.", file=sys.stderr)
        return 1

    if not os.path.exists(OOBE_FLAG):
        print("Error: OOBE setup is no longer pending.", file=sys.stderr)
        return 1

    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(f"Error parsing setup payload: {exc}", file=sys.stderr)
        return 1

    raw_fullname = str(payload.get("fullname", "")).replace(":", " ")
    fullname = " ".join(raw_fullname.split()).strip() or "Kushagra User"
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    autologin = bool(payload.get("autologin", False))
    workspace_style = str(payload.get("workspaceStyle", "classic")).strip()
    language = str(payload.get("language", "en_IN")).strip()

    if not USERNAME_RE.match(username) or username in RESERVED_USERS:
        print(f"Invalid or reserved username: {username}", file=sys.stderr)
        return 1
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1

    # Reject if user already exists to prevent accidental takeover
    try:
        pwd.getpwnam(username)
        print(f"User '{username}' already exists.", file=sys.stderr)
        return 1
    except KeyError:
        pass

    # 1. Create admin account in wheel group and set password via stdin
    run_checked(["/usr/sbin/useradd", "-m", "-G", "wheel", "-c", fullname, "-s", "/bin/bash", username])
    run_checked(["/usr/sbin/chpasswd"], input_text=f"{username}:{password}\n")

    user_info = pwd.getpwnam(username)
    home_dir = user_info.pw_dir

    # Clean up any LiveCD desktop installer link inherited from /etc/skel
    liveinst_shortcut = os.path.join(home_dir, "Desktop", "liveinst.desktop")
    if os.path.exists(liveinst_shortcut):
        os.remove(liveinst_shortcut)

    # 2. Apply locale & Fcitx5 Indic configuration
    target_locale = "hi_IN.UTF-8" if language == "hi_IN" else "en_IN.UTF-8"
    if shutil.which("localectl"):
        subprocess.run(["localectl", "set-locale", f"LANG={target_locale}"], check=False)
    configure_fcitx5(home_dir, language)

    # 3. Stage selected Plasma 6 workspace layout (Familiar vs Studio)
    stage_workspace_hook(home_dir, workspace_style)

    # 4. Fix ownership and SELinux labels on the newly populated home directory
    run_checked(["/usr/bin/chown", "-R", f"{username}:{username}", home_dir])
    if shutil.which("restorecon"):
        subprocess.run(["restorecon", "-RF", home_dir], check=False)

    # 5. Verify systemd-run, configure plasmalogin, and schedule DRM/VT-safe handoff
    # BEFORE marking OOBE_DONE / removing OOBE_FLAG so errors remain recoverable
    systemd_run_bin = shutil.which("systemd-run")
    if not systemd_run_bin:
        raise RuntimeError("systemd-run not found; cannot schedule OOBE session handoff.")

    configure_plasmalogin(username, autologin)

    handoff_script = (
        "systemctl stop plasmalogin.service 2>/dev/null || true; "
        "loginctl terminate-user kushagra-oobe 2>/dev/null || true; "
        "for _ in $(seq 1 20); do "
        "loginctl list-sessions --no-legend 2>/dev/null | grep -qE 'kushagra-oobe|plasmalogin' || break; "
        "sleep 0.5; "
        "done; "
        "udevadm settle --timeout=5 2>/dev/null || true; "
        "systemctl start plasmalogin.service"
    )
    handoff_res = subprocess.run(
        [
            systemd_run_bin,
            "--on-active=2",
            "--unit=kushagra-oobe-handoff",
            "/bin/bash",
            "-c",
            handoff_script,
        ],
        text=True,
        capture_output=True,
    )
    if handoff_res.returncode != 0:
        detail = (handoff_res.stderr or handoff_res.stdout or f"exit {handoff_res.returncode}").strip()
        raise RuntimeError(f"Failed to schedule OOBE handoff via systemd-run: {detail}")

    # 6. Mark OOBE complete permanently and disable OOBE service
    with open("/etc/plasma-setup-done", "w", encoding="utf-8") as fp:
        fp.write("done\n")
    os.chmod("/etc/plasma-setup-done", 0o644)
    with open(OOBE_DONE, "w", encoding="utf-8") as fp:
        fp.write("done\n")
    os.chmod(OOBE_DONE, 0o644)
    if os.path.exists(OOBE_FLAG):
        os.remove(OOBE_FLAG)
    subprocess.run(["systemctl", "disable", "kushagra-oobe.service"], check=False)

    return 0


if __name__ == "__main__":
    sys.exit(main())
