#!/usr/bin/env bash
set -euo pipefail

for s in \
    files/scripts/*.sh \
    files/system/usr/bin/kushagra-* \
    files/system/usr/bin/k-ai-drawer \
    files/system/usr/libexec/kushagra-setup-bootutil \
    files/system/usr/libexec/kushagra-oobe-apply \
    files/system/usr/libexec/kushagra-apply-user-layout \
    files/system/usr/libexec/kushagra-installer-autostart \
    files/system/usr/libexec/kushagra-dualboot-grub \
    files/system/usr/libexec/kushagra-flatpak-verified-init \
    files/system/usr/libexec/kushagra-fwupd-notify \
    files/system/usr/libexec/kushagra-kavach-dns \
    files/system/usr/libexec/kushagra-usbguard-setup \
    files/system/usr/libexec/kushagra-lan-mirror \
    files/system/usr/libexec/kushagra-resolve-setup \
    files/system/usr/libexec/kushagra-winapps-setup \
    files/system/usr/lib/greenboot/check/required.d/*.sh \
    files/system/usr/lib/greenboot/check/wanted.d/*.sh \
    files/system/usr/lib/greenboot/red.d/*.sh \
    files/system/usr/lib/greenboot/green.d/*.sh \
    files/system/usr/lib/systemd/system-generators/kushagra-live-plymouth-generator \
    files/system/usr/share/kushagra-os/livesys/livesys-session-extra; do
    bash -n "$s"
    echo "PASS bash -n: $s"
done

if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
    PY_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
    PY_BIN="python"
else
    echo "FAIL: neither python3 nor python interpreter found" >&2
    exit 1
fi

TMP_PYCACHE="$(mktemp -d)"
trap 'rm -rf "$TMP_PYCACHE"' EXIT
export PYTHONPYCACHEPREFIX="$TMP_PYCACHE"

for py in \
    files/system/usr/bin/k-ai-detect \
    files/system/usr/bin/k-ai-engine \
    files/system/usr/bin/k-ai-followalong \
    files/system/usr/bin/k-ai-ocr \
    files/system/usr/libexec/k-ai-broker \
    files/system/usr/libexec/k-ai-krunner \
    files/system/usr/share/kushagra-os/oobe/*.py \
    files/system/usr/share/kushagra-os/installer/*.py \
    files/system/usr/share/kushagra-os/winrun/*.py \
    files/system/usr/share/kushagra-os/apkrun/*.py \
    files/system/usr/share/kushagra-os/kai/*.py \
    files/system/usr/libexec/kushagra-installer-backend; do
    "$PY_BIN" -m py_compile "$py"
    echo "PASS py_compile: $py"
done
