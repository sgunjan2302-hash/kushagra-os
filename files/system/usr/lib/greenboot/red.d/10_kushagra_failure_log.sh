#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Greenboot Red Hook: Structured Boot Failure Diagnostics
# Records failure context to /var/log/kushagra-greenboot-failure.log and notifies stderr.

# LiveCD guard
if grep -qw "rd.live.image" /proc/cmdline 2>/dev/null; then
    exit 0
fi

LOG_FILE="/var/log/kushagra-greenboot-failure.log"
mkdir -p /var/log

# Keep failure log bounded while preserving recent incident context
if [ -f "${LOG_FILE}" ] && [ "$(wc -c < "${LOG_FILE}" 2>/dev/null || echo 0)" -gt 262144 ]; then
    tail -n 1000 "${LOG_FILE}" >| "${LOG_FILE}.tmp" && mv -f "${LOG_FILE}.tmp" "${LOG_FILE}"
fi

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo 'unknown')"
kernel_rel="$(uname -r 2>/dev/null || echo 'unknown')"

bootc_status_out="bootc unavailable"
bootc_booted_id="unknown"
if command -v bootc >/dev/null 2>&1; then
    bootc_status_out="$(bootc status 2>&1 || true)"
    if command -v python3 >/dev/null 2>&1; then
        bootc_json="$(bootc status --json 2>/dev/null || true)"
        if [ -n "${bootc_json}" ]; then
            bootc_booted_id="$(
                printf '%s' "${bootc_json}" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    b = (d.get("status") or {}).get("booted") or {}
    img = b.get("image") or {}
    if isinstance(img.get("image"), dict):
        ref = img["image"].get("image", "")
    else:
        ref = img.get("image", "")
    ver = b.get("version") or img.get("version") or ""
    dig = b.get("imageDigest") or img.get("imageDigest") or (b.get("ostree") or {}).get("checksum") or ""
    parts = [p for p in (ref, ver, dig) if p]
    print(" | ".join(parts) if parts else "unknown")
except Exception:
    print("unknown")
' 2>/dev/null || echo 'unknown'
            )"
        fi
    fi
fi

failed_units="systemctl unavailable"
if command -v systemctl >/dev/null 2>&1; then
    failed_units="$(systemctl --failed --no-legend --no-pager 2>&1 || true)"
    if [ -z "${failed_units}" ]; then
        failed_units="(none reported by systemctl --failed)"
    fi
fi

journal_errors="journalctl unavailable"
greenboot_logs="journalctl unavailable"
if command -v journalctl >/dev/null 2>&1; then
    journal_errors="$(journalctl -b -p err..emerg -n 50 --no-pager 2>&1 || true)"
    if [ -z "${journal_errors}" ]; then
        journal_errors="(no err..emerg entries in current boot journal)"
    fi
    greenboot_logs="$(journalctl -b -u 'greenboot*' -n 30 --no-pager 2>&1 || true)"
    if [ -z "${greenboot_logs}" ]; then
        greenboot_logs="(no greenboot unit entries captured)"
    fi
fi

cat <<EOF >> "${LOG_FILE}"
================================================================================
KUSHAGRA OS GREENBOOT FAILURE REPORT
STATUS: PENDING (Boot health check failed)
Timestamp: ${timestamp}
Kernel: ${kernel_rel}
Failed Deployment Booted: ${bootc_booted_id}

--- Current bootc status ---
${bootc_status_out}

--- Failed systemd units ---
${failed_units}

--- Last journal errors (err..emerg) ---
${journal_errors}

--- Greenboot unit logs ---
${greenboot_logs}

--- Automatic Rollback Explanation ---
One or more mandatory Kushagra OS health checks in /usr/lib/greenboot/check/required.d/
failed during startup. With GREENBOOT_MAX_BOOT_ATTEMPTS=2, Greenboot triggers rollback
after 1 initial failure + 2 retry boots (3 failed boots total) for a newly staged
deployment. If health checks continue to fail once those boot attempts are exhausted,
Greenboot and GRUB2 will automatically roll back to the previous known-good bootc
deployment on the next reboot.
To inspect further after recovery:
  sudo bootc status
  sudo cat /var/log/kushagra-greenboot-failure.log
  journalctl -b -1 -u 'greenboot*'
================================================================================

EOF

chmod 0644 "${LOG_FILE}" || true

cat <<EOF >&2
[KUSHAGRA-GREENBOOT][RED] Health check failed at ${timestamp} (kernel ${kernel_rel}).
[KUSHAGRA-GREENBOOT][RED] Failure diagnostics written to ${LOG_FILE}.
[KUSHAGRA-GREENBOOT][RED] System will retry or automatically roll back to the previous healthy deployment (GREENBOOT_MAX_BOOT_ATTEMPTS=2: 1 initial failure + 2 retry boots).
EOF

exit 0
