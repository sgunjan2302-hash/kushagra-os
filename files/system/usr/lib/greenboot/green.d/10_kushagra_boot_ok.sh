#!/usr/bin/env bash
set -euo pipefail

# Kushagra OS Greenboot Green Hook: Healthy Deployment Verification & Rollback Resolution
# Logs verified healthy boots to /var/log/kushagra-greenboot-status.log and resolves
# any pending failure banner in /var/log/kushagra-greenboot-failure.log.

# LiveCD guard
if grep -qw "rd.live.image" /proc/cmdline 2>/dev/null; then
    exit 0
fi

STATUS_LOG="/var/log/kushagra-greenboot-status.log"
FAILURE_LOG="/var/log/kushagra-greenboot-failure.log"
mkdir -p /var/log

timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo 'unknown')"
kernel_rel="$(uname -r 2>/dev/null || echo 'unknown')"

bootc_booted_id="unknown"
bootc_rollback_id="none"
bootc_status_out="bootc unavailable"

if command -v bootc >/dev/null 2>&1; then
    bootc_status_out="$(bootc status 2>&1 || true)"
    if command -v python3 >/dev/null 2>&1; then
        bootc_json="$(bootc status --json 2>/dev/null || true)"
        if [ -n "${bootc_json}" ]; then
            parsed_bootc="$(
                printf '%s' "${bootc_json}" | python3 -c '
import json, sys
def fmt(entry):
    if not isinstance(entry, dict):
        return ""
    img = entry.get("image") or {}
    if isinstance(img.get("image"), dict):
        ref = img["image"].get("image", "")
    else:
        ref = img.get("image", "")
    ver = entry.get("version") or img.get("version") or ""
    dig = entry.get("imageDigest") or img.get("imageDigest") or (entry.get("ostree") or {}).get("checksum") or ""
    parts = [p for p in (ref, ver, dig) if p]
    return " | ".join(parts)
try:
    d = json.load(sys.stdin)
    st = d.get("status") or {}
    print(fmt(st.get("booted")) or "unknown")
    print(fmt(st.get("rollback")) or "none")
except Exception:
    print("unknown")
    print("none")
' 2>/dev/null || printf 'unknown\nnone\n'
            )"
            bootc_booted_id="$(printf '%s\n' "${parsed_bootc}" | sed -n '1p')"
            bootc_rollback_id="$(printf '%s\n' "${parsed_bootc}" | sed -n '2p')"
        fi
    elif printf '%s\n' "${bootc_status_out}" | grep -qi 'Rollback'; then
        bootc_rollback_id="present"
    fi
fi

recovery_note="normal_green_boot"
if [ -f "${FAILURE_LOG}" ] && grep -q '^STATUS: PENDING' "${FAILURE_LOG}" 2>/dev/null; then
    last_failed_id="$(awk '/^Failed Deployment Booted: / {sub(/^Failed Deployment Booted: /, ""); val=$0} END {print val}' "${FAILURE_LOG}" 2>/dev/null || true)"
    if [ -n "${last_failed_id}" ] && [ "${last_failed_id}" != "unknown" ] \
        && [ "${bootc_booted_id}" != "unknown" ] && [ "${last_failed_id}" != "${bootc_booted_id}" ]; then
        recovery_note="rolled_back_cleanly (recovered from failed deployment: ${last_failed_id})"
    elif [ -n "${last_failed_id}" ] && [ "${last_failed_id}" != "unknown" ] \
        && [ "${bootc_booted_id}" != "unknown" ] && [ "${last_failed_id}" = "${bootc_booted_id}" ]; then
        recovery_note="recovered_on_retry"
    elif [ "${bootc_rollback_id}" != "none" ] && [ "${bootc_rollback_id}" != "" ]; then
        recovery_note="recovered_with_rollback_deployment_present (${bootc_rollback_id})"
    else
        recovery_note="recovered_on_retry"
    fi

    # Mark pending failure banners as resolved while preserving full forensic details
    awk -v ts="${timestamp}" -v note="${recovery_note}" '
        /^STATUS: PENDING/ { print "STATUS: RESOLVED (" ts " - " note ")"; next }
        { print }
    ' "${FAILURE_LOG}" >| "${FAILURE_LOG}.tmp" && mv -f "${FAILURE_LOG}.tmp" "${FAILURE_LOG}"
    chmod 0644 "${FAILURE_LOG}" || true

    cat <<EOF >> "${FAILURE_LOG}"
[RESOLVED ${timestamp}] Healthy deployment verified (${recovery_note}).
Active Deployment: ${bootc_booted_id}

EOF
    echo "[KUSHAGRA-GREENBOOT][GREEN] Previous boot failure resolved: ${recovery_note}"
fi

# Keep status log bounded to recent boot verifications
if [ -f "${STATUS_LOG}" ] && [ "$(wc -l < "${STATUS_LOG}" 2>/dev/null || echo 0)" -gt 400 ]; then
    tail -n 200 "${STATUS_LOG}" >| "${STATUS_LOG}.tmp" && mv -f "${STATUS_LOG}.tmp" "${STATUS_LOG}"
fi

cat <<EOF >> "${STATUS_LOG}"
[${timestamp}] STATUS=GREEN kernel=${kernel_rel} booted="${bootc_booted_id}" rollback="${bootc_rollback_id}" note="${recovery_note}"
EOF
chmod 0644 "${STATUS_LOG}" || true

echo "[KUSHAGRA-GREENBOOT][GREEN] Boot verified healthy at ${timestamp} (booted=${bootc_booted_id}; note=${recovery_note})."
exit 0
