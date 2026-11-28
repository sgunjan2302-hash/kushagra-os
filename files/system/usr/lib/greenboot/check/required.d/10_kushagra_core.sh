#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Greenboot Required Check: Core Immutable OS & Runtime Health
# Offline desktop-safe: strictly NO network, DNS, or external endpoint checks.

# 1. LiveCD guard: never fail greenboot on Live USB sessions
if grep -qw "rd.live.image" /proc/cmdline 2>/dev/null; then
    echo "LiveCD session detected (rd.live.image); skipping core greenboot check."
    exit 0
fi

# 2. Core bootc / OSTree deployment state
if [ -d /sysroot/ostree ] || { command -v bootc >/dev/null 2>&1 && bootc status >/dev/null 2>&1; }; then
    echo "[OK] Core bootc/ostree deployment state verified."
else
    echo "[FAIL] Core bootc/ostree state missing (/sysroot/ostree absent and bootc status failed)." >&2
    exit 1
fi

# 3. Immutable /usr read-only check (zero-mutation mount/permission verification)
usr_ro=0
if command -v findmnt >/dev/null 2>&1; then
    usr_opts="$(findmnt -n -T /usr -o OPTIONS 2>/dev/null || true)"
    if printf '%s\n' "${usr_opts}" | grep -Eq '(^|,)ro(,|$)'; then
        usr_ro=1
    fi
fi

if [ "${usr_ro}" -eq 0 ] && command -v mount >/dev/null 2>&1; then
    usr_opts="$(mount 2>/dev/null | awk '$3 == "/usr" {opts=$6} END {if (opts != "") print opts}' || true)"
    if [ -z "${usr_opts}" ]; then
        usr_opts="$(mount 2>/dev/null | awk '$3 == "/" {opts=$6} END {if (opts != "") print opts}' || true)"
    fi
    if printf '%s\n' "${usr_opts}" | tr -d '()' | grep -Eq '(^|,)ro(,|$)'; then
        usr_ro=1
    fi
fi

if [ "${usr_ro}" -eq 0 ] && [ -r /proc/mounts ]; then
    usr_opts="$(awk '$2 == "/usr" {opts=$4} END {if (opts != "") print opts}' /proc/mounts 2>/dev/null || true)"
    if [ -z "${usr_opts}" ]; then
        usr_opts="$(awk '$2 == "/" {opts=$4} END {if (opts != "") print opts}' /proc/mounts 2>/dev/null || true)"
    fi
    if printf '%s\n' "${usr_opts}" | grep -Eq '(^|,)ro(,|$)'; then
        usr_ro=1
    fi
fi

if [ "${usr_ro}" -eq 0 ] && [ ! -w /usr ]; then
    usr_ro=1
fi

if [ "${usr_ro}" -ne 1 ]; then
    echo "[FAIL] Immutable /usr filesystem is not read-only." >&2
    exit 1
fi
echo "[OK] Immutable /usr read-only protection verified."

# 4. D-Bus system bus active (brief retry for early boot ordering)
dbus_ok=0
for _ in $(seq 1 5); do
    if systemctl is-active --quiet dbus-broker.service 2>/dev/null \
        || systemctl is-active --quiet dbus.service 2>/dev/null; then
        dbus_ok=1
        break
    fi
    sleep 1
done

if [ "${dbus_ok}" -ne 1 ]; then
    echo "[FAIL] D-Bus system bus (dbus-broker.service / dbus.service) is not active." >&2
    exit 1
fi
echo "[OK] D-Bus system bus is active."

# 5. SELinux kernel security module loaded
if [ -d /sys/fs/selinux ] && { [ -e /sys/fs/selinux/enforce ] || [ -e /sys/fs/selinux/policy ]; }; then
    echo "[OK] SELinux kernel security module is loaded."
else
    echo "[FAIL] SELinux is not loaded (/sys/fs/selinux missing enforce/policy)." >&2
    exit 1
fi

exit 0
