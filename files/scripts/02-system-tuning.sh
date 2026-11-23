#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 02] Applying Kushagra OS system tuning & firewall configuration..."

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

# 2. Enforce strict permissions on hardware and sysctl drop-ins
if compgen -G "/etc/modprobe.d/*.conf" > /dev/null; then
    chmod 0644 /etc/modprobe.d/*.conf
fi

if compgen -G "/etc/sysctl.d/*.conf" > /dev/null; then
    chmod 0644 /etc/sysctl.d/*.conf
fi

if [ -f "/etc/systemd/zram-generator.conf" ]; then
    chmod 0644 "/etc/systemd/zram-generator.conf"
fi

if [ -f "/etc/environment" ]; then
    chmod 0644 "/etc/environment"
fi

# 3. Enforce executable permissions on Kushagra OS system binaries
echo "Setting executable permissions on /usr/bin/kushagra-* scripts..."
for bin in /usr/bin/kushagra-layout-switch /usr/bin/kushagra-health-check; do
    if [ -f "$bin" ]; then
        chmod 0755 "$bin"
        echo "Set 0755 permissions on $bin"
    fi
done

echo "==> [Hook 02] System tuning and firewall configuration complete."
