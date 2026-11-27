#!/usr/bin/env bash
set -euo pipefail

echo "==> [Hook 03] Configuring Kushagra OS Plymouth theme & KMS permissions..."

SPINNER_DIR="/usr/share/plymouth/themes/spinner"
THEME_DIR="/usr/share/plymouth/themes/kushagra"

mkdir -p "${THEME_DIR}"

if [ -d "${SPINNER_DIR}" ]; then
    shopt -s nullglob
    for asset in "${SPINNER_DIR}"/*.png; do
        [ -f "${asset}" ] || continue
        base="$(basename "${asset}")"
        # Preserve Kushagra OS watermark.png and never overwrite RPM-owned fedora-logos/spinner assets
        if [ "${base}" = "watermark.png" ]; then
            continue
        fi
        cp -f "${asset}" "${THEME_DIR}/${base}"
    done
    shopt -u nullglob
else
    echo "WARNING: ${SPINNER_DIR} not found; skipping spinner PNG copy." >&2
fi

for cfg in /etc/plymouth/plymouthd.conf /etc/dracut.conf.d/plymouth-kms.conf; do
    if [ -f "${cfg}" ]; then
        chmod 0644 "${cfg}"
    fi
done
chmod 0755 "${THEME_DIR}"
find "${THEME_DIR}" -maxdepth 1 -type f -exec chmod 0644 {} +

shopt -s nullglob
spinner_frames=("${THEME_DIR}"/animation-*.png "${THEME_DIR}"/throbber-*.png)
shopt -u nullglob

THEME_READY=0
if [ -f "${THEME_DIR}/kushagra.plymouth" ] \
    && [ -f "${THEME_DIR}/watermark.png" ] \
    && [ "${#spinner_frames[@]}" -gt 0 ] \
    && grep -q '^UseFirmwareBackground=true$' "${THEME_DIR}/kushagra.plymouth"; then
    THEME_READY=1
fi

if command -v plymouth-set-default-theme >/dev/null 2>&1; then
    if [ "${THEME_READY}" -eq 1 ] && plymouth-set-default-theme kushagra; then
        echo "Activated Plymouth theme: kushagra (UseFirmwareBackground=true)"
    else
        echo "WARNING: Kushagra Plymouth theme assets missing or activation failed; falling back to bgrt." >&2
        plymouth-set-default-theme bgrt || {
            if [ -f /etc/plymouth/plymouthd.conf ]; then
                sed -i 's/^Theme=.*/Theme=bgrt/' /etc/plymouth/plymouthd.conf || true
            fi
        }
    fi
else
    echo "WARNING: plymouth-set-default-theme not found." >&2
    if [ "${THEME_READY}" -ne 1 ] && [ -f /etc/plymouth/plymouthd.conf ]; then
        sed -i 's/^Theme=.*/Theme=bgrt/' /etc/plymouth/plymouthd.conf || true
    fi
fi

echo "==> [Hook 03] Plymouth theme configuration complete."
