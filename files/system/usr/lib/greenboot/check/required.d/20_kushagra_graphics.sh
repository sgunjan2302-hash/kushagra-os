#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Greenboot Required Check: DRM Graphics & Display Manager Readiness
# Ensures the desktop login manager (plasmalogin / display-manager) starts on a working DRM node.

# 1. LiveCD guard: never fail greenboot on Live USB sessions
if grep -qw "rd.live.image" /proc/cmdline 2>/dev/null; then
    echo "LiveCD session detected (rd.live.image); skipping graphics greenboot check."
    exit 0
fi

# 2. Verify DRM graphics node (/dev/dri/card*), retrying briefly up to 10s for udev
drm_ready=0
for _ in $(seq 1 10); do
    shopt -s nullglob
    for card in /dev/dri/card*; do
        if [ -c "${card}" ]; then
            drm_ready=1
            break
        fi
    done
    shopt -u nullglob
    if [ "${drm_ready}" -eq 1 ]; then
        break
    fi
    sleep 1
done

if [ "${drm_ready}" -ne 1 ]; then
    echo "[FAIL] No DRM graphics device (/dev/dri/card*) found after 10s." >&2
    exit 1
fi
echo "[OK] DRM graphics device node detected."

# 3. Wait up to 35s for plasmalogin.service or display-manager.service to become active
dm_ready=0
for _ in $(seq 1 35); do
    if systemctl is-active --quiet plasmalogin.service 2>/dev/null \
        || systemctl is-active --quiet display-manager.service 2>/dev/null; then
        dm_ready=1
        break
    fi
    sleep 1
done

if [ "${dm_ready}" -ne 1 ]; then
    echo "[FAIL] Display manager (plasmalogin.service / display-manager.service) failed to become active within 35s." >&2
    exit 1
fi

echo "[OK] Display manager is active."
exit 0
