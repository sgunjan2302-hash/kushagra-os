#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Greenboot Wanted Check: Desktop & Low-RAM Sanity Warnings
# Non-fatal informational checks only; this script MUST always exit 0.

# 1. LiveCD guard
if grep -qw "rd.live.image" /proc/cmdline 2>/dev/null; then
    echo "LiveCD session detected (rd.live.image); skipping desktop sanity check."
    exit 0
fi

echo "Running Kushagra OS desktop sanity checks (non-fatal)..."

# 2. ZRAM compressed swap (/dev/zram0)
if command -v zramctl >/dev/null 2>&1; then
    zram_info="$(zramctl --noheadings --output NAME,ALGORITHM,DISKSIZE /dev/zram0 2>/dev/null || true)"
    if [ -n "${zram_info}" ]; then
        echo "[OK] ZRAM swap device active: ${zram_info}"
    else
        echo "[WARN] /dev/zram0 is not active according to zramctl."
    fi
else
    echo "[WARN] zramctl utility not found."
fi

# 3. earlyoom service
if systemctl is-active --quiet earlyoom.service 2>/dev/null; then
    echo "[OK] earlyoom.service is active."
else
    echo "[WARN] earlyoom.service is not active."
fi

# 4. Global K-AI lazy socket activation (must be enabled globally, never eager service)
if systemctl --global is-enabled k-ai-engine.socket >/dev/null 2>&1; then
    echo "[OK] Global k-ai-engine.socket is enabled."
else
    echo "[WARN] Global k-ai-engine.socket is not enabled."
fi

# 5. Kushagra Liquid Glass hardware/low-RAM guard
if [ -x /usr/bin/kushagra-glass-guard ]; then
    if systemctl --global is-enabled kushagra-glass-guard.service >/dev/null 2>&1; then
        echo "[OK] kushagra-glass-guard binary and global user service are ready."
    else
        echo "[WARN] /usr/bin/kushagra-glass-guard is executable, but global kushagra-glass-guard.service is not enabled."
    fi
else
    echo "[WARN] /usr/bin/kushagra-glass-guard is missing or not executable."
fi

# 6. firewalld service
if systemctl is-active --quiet firewalld.service 2>/dev/null; then
    echo "[OK] firewalld.service is active."
else
    echo "[WARN] firewalld.service is not active."
fi

exit 0
