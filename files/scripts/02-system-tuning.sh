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

for cfg in /etc/systemd/zram-generator.conf /etc/environment /etc/polkit-1/rules.d/50-kushagra-oobe.rules; do
    if [ -f "$cfg" ]; then
        chmod 0644 "$cfg"
    fi
done

# 3. Enforce executable permissions on Kushagra OS system binaries & OOBE helpers
echo "Setting executable permissions on Kushagra OS scripts..."
for bin in \
    /usr/bin/kushagra-layout-switch \
    /usr/bin/kushagra-health-check \
    /usr/bin/kushagra-setup \
    /usr/libexec/kushagra-setup-bootutil \
    /usr/libexec/kushagra-oobe-apply \
    /usr/libexec/kushagra-apply-user-layout; do
    if [ -f "$bin" ]; then
        chmod 0755 "$bin"
        echo "Set 0755 permissions on $bin"
    fi
done

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
mkdir -p /var/lib /etc/plasmalogin.conf.d
touch /var/lib/kushagra-oobe-pending
chmod 0644 /var/lib/kushagra-oobe-pending

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

echo "==> [Hook 02] System tuning, security isolation & OOBE configuration complete."
