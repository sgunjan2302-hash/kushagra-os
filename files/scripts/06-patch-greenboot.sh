#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 06] Patching greenboot GRUB static config & verifying greenboot permissions..."

# Workaround for greenboot-rs#218:
# Ensure /usr/lib/bootupd/grub2-static/configs.d/08_greenboot.cfg ends with a
# trailing newline (\n) so bootupd static GRUB config concatenation never merges
# the final directive with the next snippet.
GREENBOOT_GRUB_CFG="${GREENBOOT_GRUB_CFG:-/usr/lib/bootupd/grub2-static/configs.d/08_greenboot.cfg}"

if [ ! -f "${GREENBOOT_GRUB_CFG}" ]; then
    echo "Skipped: ${GREENBOOT_GRUB_CFG} not present (no patch required)."
elif [ ! -s "${GREENBOOT_GRUB_CFG}" ]; then
    echo "Skipped: ${GREENBOOT_GRUB_CFG} is empty (0 bytes; no patch required)."
elif [ "$(tail -c 1 "${GREENBOOT_GRUB_CFG}" | wc -l)" -eq 0 ]; then
    printf '\n' >> "${GREENBOOT_GRUB_CFG}"
    if [ "$(tail -c 1 "${GREENBOOT_GRUB_CFG}" | wc -l)" -eq 1 ]; then
        echo "Patched: appended trailing newline to ${GREENBOOT_GRUB_CFG} (greenboot-rs#218)."
    else
        echo "ERROR: Failed to verify trailing newline on ${GREENBOOT_GRUB_CFG}" >&2
        exit 1
    fi
else
    echo "Already clean: ${GREENBOOT_GRUB_CFG} already ends with a trailing newline."
fi

# Enforce clean permissions on Kushagra OS greenboot configs & hooks if present
for cfg in \
    /etc/greenboot/greenboot.conf \
    /usr/lib/systemd/system/greenboot-set-rollback-trigger.service.d/10-kushagra-shutdown.conf; do
    if [ -f "${cfg}" ]; then
        chmod 0644 "${cfg}"
    fi
done

for script in \
    /usr/lib/greenboot/check/required.d/10_kushagra_core.sh \
    /usr/lib/greenboot/check/required.d/20_kushagra_graphics.sh \
    /usr/lib/greenboot/check/wanted.d/10_kushagra_desktop_sanity.sh \
    /usr/lib/greenboot/red.d/10_kushagra_failure_log.sh \
    /usr/lib/greenboot/green.d/10_kushagra_boot_ok.sh; do
    if [ -f "${script}" ]; then
        chmod 0755 "${script}"
    fi
done

# Enable installed greenboot-rs systemd units safely if present
if command -v systemctl >/dev/null 2>&1; then
    for unit in \
        greenboot.service \
        greenboot-healthcheck.service \
        greenboot-task-runner.service \
        greenboot-set-rollback-trigger.service \
        greenboot-grub2-set-counter.service \
        greenboot-grub2-set-success.service \
        greenboot-status.service; do
        if systemctl list-unit-files "${unit}" >/dev/null 2>&1; then
            systemctl enable "${unit}" 2>/dev/null || true
        fi
    done
fi

echo "==> [Hook 06] Greenboot configuration & GRUB snippet check complete."
