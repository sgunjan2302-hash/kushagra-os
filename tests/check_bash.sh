#!/usr/bin/env bash
set -euo pipefail

for s in \
    files/scripts/*.sh \
    files/system/usr/bin/kushagra-* \
    files/system/usr/libexec/kushagra-setup-bootutil \
    files/system/usr/libexec/kushagra-oobe-apply \
    files/system/usr/libexec/kushagra-apply-user-layout \
    files/system/usr/libexec/kushagra-installer-autostart \
    files/system/usr/share/kushagra-os/livesys/livesys-session-extra; do
    bash -n "$s"
    echo "PASS bash -n: $s"
done

for py in \
    files/system/usr/share/kushagra-os/oobe/*.py \
    files/system/usr/share/kushagra-os/installer/*.py \
    files/system/usr/share/kushagra-os/winrun/*.py \
    files/system/usr/libexec/kushagra-installer-backend; do
    python3 -m py_compile "$py"
    echo "PASS py_compile: $py"
done
