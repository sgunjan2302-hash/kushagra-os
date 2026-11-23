#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 01] Configuring Fcitx5 Wayland integration for Kushagra OS..."

# Disable duplicate XDG autostart to prevent KWin conflict warnings on Wayland login
# Under KDE Plasma 6 Wayland, KWin natively starts Fcitx5 as the active input method compositor
if [ -f "/etc/xdg/autostart/org.fcitx.Fcitx5.desktop" ]; then
    echo "Neutralizing duplicate autostart: /etc/xdg/autostart/org.fcitx.Fcitx5.desktop"
    rm -f "/etc/xdg/autostart/org.fcitx.Fcitx5.desktop"
else
    echo "XDG autostart file for Fcitx5 not present; no cleanup required."
fi

# Ensure skeleton kwinrc exists and has correct permissions
if [ -f "/etc/skel/.config/kwinrc" ]; then
    chmod 0644 "/etc/skel/.config/kwinrc"
    echo "Verified permissions for /etc/skel/.config/kwinrc"
fi

echo "==> [Hook 01] Fcitx5 Wayland configuration complete."
