#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 01] Configuring Fcitx5 Wayland & Plasma 6 defaults for Kushagra OS..."

# Disable duplicate XDG autostart to prevent KWin conflict warnings on Wayland login
# Under KDE Plasma 6 Wayland, KWin natively starts Fcitx5 as the active input method compositor
if [ -f "/etc/xdg/autostart/org.fcitx.Fcitx5.desktop" ]; then
    echo "Neutralizing duplicate autostart: /etc/xdg/autostart/org.fcitx.Fcitx5.desktop"
    rm -f "/etc/xdg/autostart/org.fcitx.Fcitx5.desktop"
else
    echo "XDG autostart file for Fcitx5 not present; no cleanup required."
fi

# Ensure system-wide XDG autostart suppression for Plasma Welcome Center stays intact
# (Keep /usr/share/applications/org.kde.plasma-welcome.desktop intact for manual launch)
mkdir -p /etc/xdg/autostart
if [ ! -f "/etc/xdg/autostart/org.kde.plasma-welcome.desktop" ] || ! grep -q '^Hidden=true$' "/etc/xdg/autostart/org.kde.plasma-welcome.desktop"; then
    cat << 'WELCOME_AUTOSTART_EOF' > /etc/xdg/autostart/org.kde.plasma-welcome.desktop
[Desktop Entry]
Type=Application
Name=Welcome Center
Hidden=true
WELCOME_AUTOSTART_EOF
    echo "Enforced Hidden=true in /etc/xdg/autostart/org.kde.plasma-welcome.desktop"
fi

# Dynamically synchronize plasma-welcome LastSeenVersion to the installed RPM version
if command -v rpm >/dev/null 2>&1 && rpm -q plasma-welcome >/dev/null 2>&1; then
    PW_VER="$(rpm -q --qf '%{VERSION}' plasma-welcome 2>/dev/null || true)"
    if [ -n "${PW_VER}" ] && [[ "${PW_VER}" =~ ^[0-9]+([._~-][0-9A-Za-z]+)*$ ]]; then
        for welcomerc in /etc/xdg/plasma-welcomerc /etc/skel/.config/plasma-welcomerc; do
            if [ -f "${welcomerc}" ]; then
                if grep -q '^LastSeenVersion=' "${welcomerc}"; then
                    sed -i "s|^LastSeenVersion=.*|LastSeenVersion=${PW_VER}|" "${welcomerc}"
                else
                    echo "LastSeenVersion=${PW_VER}" >> "${welcomerc}"
                fi
                echo "Synchronized LastSeenVersion=${PW_VER} in ${welcomerc}"
            fi
        done
    else
        echo "Notice: Unexpected plasma-welcome RPM version '${PW_VER}'; retaining default LastSeenVersion."
    fi
else
    echo "Notice: plasma-welcome RPM not installed or rpm unavailable; retaining default LastSeenVersion."
fi

# Enforce clean permissions on Fcitx5, KWin, Welcome suppression, global shortcuts, and APK handler files
for cfg_dir in /etc/skel/.config/fcitx5 /usr/share/kushagra-os/apkrun; do
    if [ -d "${cfg_dir}" ]; then
        chmod 0755 "${cfg_dir}"
    fi
done

for cfg in \
    /etc/xdg/kwinrc \
    /etc/skel/.config/kwinrc \
    /etc/skel/.config/fcitx5/profile \
    /etc/xdg/kglobalshortcutsrc \
    /etc/skel/.config/kglobalshortcutsrc \
    /etc/xdg/autostart/org.kde.plasma-welcome.desktop \
    /etc/xdg/plasma-welcomerc \
    /etc/skel/.config/plasma-welcomerc \
    /etc/xdg/kded6rc \
    /usr/share/applications/kushagra-apkrun.desktop \
    /usr/share/kushagra-os/apkrun/main.py; do
    if [ -f "${cfg}" ]; then
        chmod 0644 "${cfg}"
        echo "Verified 0644 permissions for ${cfg}"
    fi
done

if [ -f "/usr/bin/kushagra-apkrun" ]; then
    chmod 0755 "/usr/bin/kushagra-apkrun"
    echo "Verified 0755 permissions for /usr/bin/kushagra-apkrun"
fi

echo "==> [Hook 01] Fcitx5 Wayland & Plasma 6 configuration complete."
