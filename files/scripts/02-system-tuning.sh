#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 02] Applying Kushagra OS system tuning, security & OOBE isolation..."

# 1. Configure firewalld DefaultZone to kushagra-workstation
FIREWALLD_CONF="/etc/firewalld/firewalld.conf"
if [ -f "${FIREWALLD_CONF}" ]; then
    echo "Updating DefaultZone in ${FIREWALLD_CONF} to kushagra-workstation..."
    sed -i 's/^DefaultZone=.*/DefaultZone=kushagra-workstation/' "${FIREWALLD_CONF}"
    if ! grep -q "^DefaultZone=kushagra-workstation" "${FIREWALLD_CONF}"; then
        echo "DefaultZone=kushagra-workstation not matched by sed, appending directly..."
        echo "DefaultZone=kushagra-workstation" >> "${FIREWALLD_CONF}"
    fi
    echo "Verified firewalld DefaultZone setting:"
    grep "^DefaultZone=" "${FIREWALLD_CONF}"
else
    echo "Notice: ${FIREWALLD_CONF} not present at build-time; creating directory and file..."
    mkdir -p /etc/firewalld
    echo "DefaultZone=kushagra-workstation" > "${FIREWALLD_CONF}"
    chmod 0644 "${FIREWALLD_CONF}"
fi

# 2. Enforce strict permissions on hardware, sysctl, polkit, and systemd overlays
if compgen -G "/etc/modprobe.d/*.conf" > /dev/null; then
    chmod 0644 /etc/modprobe.d/*.conf
fi

if compgen -G "/etc/sysctl.d/*.conf" > /dev/null; then
    chmod 0644 /etc/sysctl.d/*.conf
fi

for cfg in \
    /etc/systemd/zram-generator.conf \
    /etc/environment \
    /etc/polkit-1/rules.d/50-kushagra-oobe.rules \
    /etc/polkit-1/rules.d/50-kushagra-installer.rules \
    /etc/polkit-1/rules.d/50-kushagra-kavach.rules \
    /etc/polkit-1/rules.d/50-kushagra-kai.rules \
    /etc/anaconda/profile.d/kushagra-os.conf \
    /etc/modules-load.d/90-kushagra-ntsync.conf \
    /etc/udev/rules.d/90-kushagra-ntsync.rules \
    /etc/xdg/mimeapps.list \
    /etc/xdg/kwinrc \
    /etc/xdg/kwinrulesrc \
    /etc/xdg/kdeglobals \
    /etc/xdg/kglobalshortcutsrc \
    /etc/xdg/kded6rc \
    /etc/xdg/plasma-welcomerc \
    /etc/xdg/autostart/org.kde.plasma-welcome.desktop \
    /etc/systemd/resolved.conf.d/10-dot-opportunistic.conf \
    /etc/systemd/system/system-flatpak-setup.service.d/10-skip-livecd.conf \
    /etc/systemd/system/system-flatpak-setup.timer.d/10-skip-livecd.conf \
    /etc/systemd/system/bootloader-update.service.d/10-kushagra-live-guard.conf \
    /etc/systemd/system/usbguard.service.d/10-kushagra-safe.conf \
    /etc/plymouth/plymouthd.conf \
    /etc/dracut.conf.d/plymouth-kms.conf \
    /usr/lib/bootc/kargs.d/10-kushagra-boot.toml \
    /usr/lib/systemd/user/kushagra-installer.service \
    /usr/lib/systemd/user/kushagra-oobe-ui.service \
    /usr/lib/systemd/user/kushagra-glass-guard.service \
    /usr/lib/systemd/user/k-ai-engine.socket \
    /usr/lib/systemd/user/k-ai-engine.service \
    /usr/lib/systemd/system/kushagra-dualboot-detect.service \
    /usr/lib/tmpfiles.d/kushagra-kavach.conf \
    /usr/share/plymouth/themes/kushagra/kushagra.plymouth \
    /usr/share/plymouth/themes/kushagra/watermark.png \
    /usr/share/pixmaps/kushagra-logo.png \
    /usr/share/color-schemes/KushagraGlassDark.colors \
    /usr/share/color-schemes/KushagraGlassLight.colors \
    /usr/share/kushagra-os/kai/actions.json \
    /usr/share/kushagra-os/kai/main.py \
    /usr/share/kushagra-os/kai/Main.qml \
    /usr/share/kio/servicemenus/kushagra-kavach-scan.desktop \
    /usr/share/kio/servicemenus/kushagra-resolve-convert.desktop \
    /usr/share/applications/kushagra-apkrun.desktop \
    /usr/share/applications/k-ai-drawer.desktop \
    /usr/share/applications/k-ai-followalong.desktop \
    /usr/share/applications/k-ai-ocr.desktop \
    /usr/share/applications/kushagra-reboot-windows.desktop \
    /usr/share/krunner/dbusplugins/k-ai-krunner.desktop \
    /usr/share/dbus-1/services/org.kushagraos.KAI.Runner.service \
    /etc/skel/.config/kwinrc \
    /etc/skel/.config/kglobalshortcutsrc \
    /etc/skel/.config/fcitx5/profile \
    /etc/skel/.config/plasma-welcomerc \
    /etc/skel/.config/ksplashrc \
    /etc/greenboot/greenboot.conf \
    /usr/lib/systemd/system/greenboot-set-rollback-trigger.service.d/10-kushagra-shutdown.conf \
    /etc/containers/registries.conf.d/50-kushagra-mirror.conf \
    /usr/share/kushagra-os/bazaar/config.yaml \
    /usr/share/kushagra-os/bazaar/blocklist.yaml \
    /usr/lib/systemd/system/kushagra-flatpak-verified-init.service \
    /usr/lib/systemd/user/kushagra-fwupd-notify.service \
    /usr/lib/systemd/user/kushagra-fwupd-notify.timer \
    /usr/lib/systemd/user-preset/85-kushagra-dx.preset; do
    if [ -f "$cfg" ]; then
        chmod 0644 "$cfg"
    fi
done

if [ -d /usr/share/kushagra-os/kai ]; then
    chmod 0755 /usr/share/kushagra-os/kai
fi

# 3. Enforce executable permissions on Kushagra OS system binaries & OOBE/Installer helpers
echo "Setting executable permissions on Kushagra OS scripts..."
for bin in \
    /usr/bin/kushagra-layout-switch \
    /usr/bin/kushagra-health-check \
    /usr/bin/kushagra-setup \
    /usr/bin/kushagra-installer \
    /usr/bin/kushagra-winrun \
    /usr/bin/kushagra-apkrun \
    /usr/bin/kushagra-kavach-scan \
    /usr/bin/kushagra-glass-toggle \
    /usr/bin/kushagra-glass-guard \
    /usr/bin/k-ai-detect \
    /usr/bin/k-ai-engine \
    /usr/bin/k-ai-drawer \
    /usr/bin/k-ai-followalong \
    /usr/bin/k-ai-ocr \
    /usr/bin/kushagra-resolve-convert \
    /usr/bin/kushagra-reboot-windows \
    /usr/libexec/kushagra-setup-bootutil \
    /usr/libexec/kushagra-oobe-apply \
    /usr/libexec/kushagra-apply-user-layout \
    /usr/libexec/kushagra-installer-autostart \
    /usr/libexec/kushagra-installer-backend \
    /usr/libexec/kushagra-kavach-dns \
    /usr/libexec/kushagra-usbguard-setup \
    /usr/libexec/kushagra-lan-mirror \
    /usr/libexec/k-ai-broker \
    /usr/libexec/k-ai-krunner \
    /usr/libexec/kushagra-resolve-setup \
    /usr/libexec/kushagra-winapps-setup \
    /usr/libexec/kushagra-dualboot-grub \
    /usr/libexec/kushagra-flatpak-verified-init \
    /usr/libexec/kushagra-fwupd-notify \
    /usr/bin/kushagra-mok-enroll \
    /usr/bin/kushagra-eac-status \
    /usr/bin/kushagra-eac-mode \
    /usr/lib/greenboot/check/required.d/10_kushagra_core.sh \
    /usr/lib/greenboot/check/required.d/20_kushagra_graphics.sh \
    /usr/lib/greenboot/check/wanted.d/10_kushagra_desktop_sanity.sh \
    /usr/lib/greenboot/red.d/10_kushagra_failure_log.sh \
    /usr/lib/greenboot/green.d/10_kushagra_boot_ok.sh \
    /usr/lib/systemd/system-generators/kushagra-live-plymouth-generator; do
    if [ -f "$bin" ]; then
        chmod 0755 "$bin"
        echo "Set 0755 permissions on $bin"
    fi
done

# Enable on-demand freshclam execution by neutralizing sample Example sentinel without baking /var DB
if [ -f /etc/freshclam.conf ]; then
    sed -i -E 's/^[[:space:]]*Example([[:space:]]|$)/#Example\1/' /etc/freshclam.conf
fi

# Strictly keep USBGuard opt-in (disabled by default until HID whitelist generated via ujust setup-usbguard)
systemctl disable usbguard.service 2>/dev/null || true

# Wire Bazaar Verified Flathub config + hide Flatpak VS Code (DX ships native code RPM)
mkdir -p /etc/bazaar /usr/share/ublue-os/bazaar
if [ -f /usr/share/kushagra-os/bazaar/config.yaml ]; then
    cp -f /usr/share/kushagra-os/bazaar/config.yaml /etc/bazaar/config.yaml
    cp -f /usr/share/kushagra-os/bazaar/config.yaml /usr/share/ublue-os/bazaar/main.yaml
    chmod 0644 /etc/bazaar/config.yaml /usr/share/ublue-os/bazaar/main.yaml
fi
if [ -f /usr/share/kushagra-os/bazaar/blocklist.yaml ]; then
    cp -f /usr/share/kushagra-os/bazaar/blocklist.yaml /etc/bazaar/blocklist.yaml
    chmod 0644 /etc/bazaar/blocklist.yaml
fi

# Disable DiscoverNotifier autostart (KDE Bug 509180 RAM leak & Bug 522169 fwupd hang);
# replaced by lightweight kushagra-fwupd-notify.timer
mkdir -p /etc/xdg/autostart
cat <<'EOF' > /etc/xdg/autostart/org.kde.discover.notifier.desktop
[Desktop Entry]
Type=Application
Name=Discover Notifier
Hidden=true
NoDisplay=true
EOF
chmod 0644 /etc/xdg/autostart/org.kde.discover.notifier.desktop

# Keep nouveau unblacklisted in base/DX images lacking NVIDIA kernel modules;
# recipe-nvidia.yml / recipe-dx-nvidia.yml install NVIDIA akmods and copy 10-kushagra-nvidia.toml before initramfs.
if [ -z "$(find /usr/lib/modules -maxdepth 4 \( -name 'nvidia.ko*' -o -name 'nvidia-open*' \) -print -quit 2>/dev/null || true)" ]; then
    rm -f /usr/lib/bootc/kargs.d/10-kushagra-nvidia.toml
fi

# Enable K-AI lazy inference socket globally (0 MB idle model RAM; never enable k-ai-engine.service directly)
# and wire v0.5.0 Verified Flathub + LVFS firmware timer
if command -v systemctl >/dev/null 2>&1; then
    systemctl --global enable k-ai-engine.socket 2>/dev/null || true
    systemctl --global disable k-ai-engine.service 2>/dev/null || true
    systemctl enable kushagra-dualboot-detect.service 2>/dev/null || true
    systemctl enable kushagra-flatpak-verified-init.service 2>/dev/null || true
    systemctl unmask fwupd.service 2>/dev/null || true
    systemctl enable fwupd.service fwupd-refresh.timer 2>/dev/null || true
    systemctl --global enable kushagra-fwupd-notify.timer 2>/dev/null || true
fi

# Refresh desktop & MIME association caches for .exe/.msi WinRun and K-Installer handlers
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database /usr/share/mime || true
fi

# 4. Security & LiveCD Isolation (Strictly activated ONLY under rd.live.image)
echo "Locking root password in base image (no baked blank-password backdoors)..."
passwd -l root || true

# Configure livesys-scripts strictly for LiveCD-only liveuser + plasmalogin autologin
mkdir -p /etc/sysconfig /var/lib/livesys
echo 'livesys_session="kde"' > /etc/sysconfig/livesys
chmod 0644 /etc/sysconfig/livesys

# Configure LiveCD-only NOPASSWD sudoers via livesys-session-extra (sourced ONLY when rd.live.image)
# Source template is also materialized via /usr/lib/tmpfiles.d/kushagra-oobe.conf for bootc images.
if [ -f /usr/share/kushagra-os/livesys/livesys-session-extra ]; then
    chmod 0755 /usr/share/kushagra-os/livesys/livesys-session-extra
    cp -f /usr/share/kushagra-os/livesys/livesys-session-extra /var/lib/livesys/livesys-session-extra
    chmod 0755 /var/lib/livesys/livesys-session-extra
fi

# Enable LiveCD-only livesys services (both gated on ConditionKernelCommandLine=rd.live.image)
systemctl enable livesys.service livesys-late.service || true

# 5. Prepare Kushagra First-Boot OOBE Wizard & Inhibit Upstream Plasma Setup
echo "Preparing Kushagra OS First-Boot OOBE Wizard..."
# Do not bake runtime /var/lib/kushagra-oobe-pending state into the container image; K-Installer %post creates it on install
mkdir -p /etc/plasmalogin.conf.d

# Inhibit Fedora upstream plasma-setup.service so kushagra-oobe runs exclusively
touch /etc/plasma-setup-done
systemctl disable plasma-setup.service 2>/dev/null || true
systemctl enable kushagra-oobe.service || true

# Create sysuser/tmpfiles if systemd-sysusers is available at build-time
if command -v systemd-sysusers >/dev/null 2>&1 && [ -f /usr/lib/sysusers.d/kushagra-oobe.conf ]; then
    systemd-sysusers /usr/lib/sysusers.d/kushagra-oobe.conf || true
fi

# Ensure Desktop liveinst shortcut permission for skeleton / LiveCD compatibility
mkdir -p /etc/skel/Desktop
if [ -f "/etc/skel/Desktop/liveinst.desktop" ]; then
    chmod 0755 /etc/skel/Desktop/liveinst.desktop
fi

# 6. Kernel Modules Hygiene for BlueBuild initramfs & LiveCD dracut
# Upstream base images occasionally carry an orphan/partial /usr/lib/modules/<kver> directory
# (e.g., an out-of-tree module remnant) lacking vmlinuz or core modules like overlay.
# BlueBuild's initramfs module runs dracut on every /usr/lib/modules/* directory; remove only
# incomplete/orphan directories while strictly verifying at least one complete kernel remains.
echo "Auditing /usr/lib/modules for BlueBuild initramfs compatibility..."
ls -la /usr/lib/modules || true
rpm -qa 'kernel*' || true

COMPLETE_KERNELS=()
INCOMPLETE_KERNELS=()
for kdir in /usr/lib/modules/*/; do
    [ -d "$kdir" ] || continue
    kver="$(basename "${kdir%/}")"
    has_overlay=0
    if [ -n "$(find "$kdir" -name 'overlay.ko*' -print -quit 2>/dev/null || true)" ] || \
       { [ -f "${kdir}modules.builtin" ] && grep -q 'overlay\.ko' "${kdir}modules.builtin" 2>/dev/null; }; then
        has_overlay=1
    fi
    if [ -f "${kdir}vmlinuz" ] && [ "$has_overlay" -eq 1 ]; then
        COMPLETE_KERNELS+=("$kdir")
    else
        INCOMPLETE_KERNELS+=("$kdir")
        echo "Warning: Detected incomplete/orphan kernel module directory: ${kver}"
    fi
done

if [ "${#COMPLETE_KERNELS[@]}" -ge 1 ] && [ "${#INCOMPLETE_KERNELS[@]}" -ge 1 ]; then
    for kdir in "${INCOMPLETE_KERNELS[@]}"; do
        echo "Pruning incomplete kernel module directory to prevent initramfs/dracut failure: ${kdir}"
        rm -rf -- "$kdir"
    done
elif [ "${#COMPLETE_KERNELS[@]}" -eq 0 ]; then
    echo "Notice: No complete vmlinuz+overlay kernel detected; skipping pruning for safety."
fi

echo "==> [Hook 02] System tuning, security isolation & OOBE configuration complete."
