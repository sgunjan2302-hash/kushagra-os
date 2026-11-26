#!/usr/bin/env python3
"""Deterministic Kickstart generator for Kushagra OS Stage 1 K-Installer."""

import os
import re

SAFE_DEV_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _check_kname(name: str, role: str) -> str:
    clean = os.path.basename((name or "").strip())
    if not clean or clean in {".", ".."} or not SAFE_DEV_RE.match(clean):
        raise ValueError(f"Unsafe kernel device name for {role}: {name!r}")
    return clean


def build_kickstart(target: dict) -> str:
    """Build a non-interactive Fedora 44 Kickstart preserving neighbors & enabling Stage 2 OOBE."""
    kind = target.get("kind")
    disk_kname = _check_kname(target.get("diskKname", ""), "disk")
    esp_kname = (target.get("espKname") or "").strip()
    if esp_kname:
        esp_kname = _check_kname(esp_kname, "esp")

    esp_disk_raw = (target.get("espDiskKname") or "").strip()
    if esp_disk_raw:
        esp_disk_kname = _check_kname(esp_disk_raw, "esp disk")
    elif esp_kname and not re.match(rf"^{re.escape(disk_kname)}p?\d+$", esp_kname):
        esp_disk_kname = re.sub(r"(?<=\d)p\d+$|\d+$", "", esp_kname)
    else:
        esp_disk_kname = disk_kname

    only_use_disks = [disk_kname]
    if esp_kname and esp_disk_kname and esp_disk_kname != disk_kname:
        only_use_disks.append(esp_disk_kname)

    storage_lines = [
        "# Preserve all existing disks, Windows partitions, and EFI entries",
        f"ignoredisk --only-use={','.join(only_use_disks)}",
        "clearpart --none",
        "# bootc images keep kernel in /usr/lib/modules/*/vmlinuz, so %post deterministically stages",
        "# kernel, initramfs, grub2, grubenv, and dual-boot-safe EFI without invoking Anaconda's",
        "# /boot/vmlinuz-* bug or touching Windows Boot Manager",
        "bootloader --location=none",
    ]

    if esp_kname:
        storage_lines.append(f'part /boot/efi --fstype="efi" --onpart={esp_kname} --noformat')
    elif kind == "unallocated":
        storage_lines.append(f'part /boot/efi --fstype="efi" --size=512 --ondisk={disk_kname}')
    else:
        raise ValueError("Cannot install into a single pre-existing partition without an existing EFI System Partition.")

    if kind == "unallocated":
        storage_lines.extend([
            f'part /boot --fstype="ext4" --size=1024 --ondisk={disk_kname}',
            f'part btrfs.01 --fstype="btrfs" --size=8192 --grow --ondisk={disk_kname}',
        ])
    elif kind == "partition":
        part_kname = _check_kname(target.get("partKname", ""), "target partition")
        # Single non-Windows/non-EFI partition reclaimed cleanly; /boot resides on Btrfs root (Fedora GRUB2 supported)
        storage_lines.append(f'part btrfs.01 --fstype="btrfs" --onpart={part_kname}')
    else:
        raise ValueError(f"Unsupported target kind: {kind!r}")

    storage_lines.extend([
        "btrfs none --label=kushagra_os --data=single btrfs.01",
        "btrfs / --subvol --name=root kushagra_os",
        "btrfs /var --subvol --name=var kushagra_os",
        "btrfs /var/home --subvol --name=home kushagra_os",
    ])

    post_block = r"""%post --erroronfail
set -eu

echo "KUSHAGRA_POST: stripping transient LiveCD session artifacts"
rm -f /etc/sudoers.d/90-liveuser
rm -rf /var/home/liveuser /home/liveuser
if id liveuser >/dev/null 2>&1; then
    userdel -f liveuser 2>/dev/null || true
fi
if [ -f /etc/plasmalogin.conf ]; then
    sed -i -E 's/^User=liveuser$/#User=/; s/^Session=plasma\.desktop$/#Session=/' /etc/plasmalogin.conf
fi
rm -f /etc/plasmalogin.conf.d/00-kushagra-oobe.conf /etc/plasmalogin.conf.d/10-user-autologin.conf /etc/plasmalogin.conf.d/*live*.conf
if [ -d /etc/plasmalogin.conf.d ]; then
    grep -rl "liveuser" /etc/plasmalogin.conf.d 2>/dev/null | xargs -r rm -f || true
fi

echo "KUSHAGRA_POST: initializing /var subvolume hierarchy and machine-id"
mkdir -p /var/home /var/lib /var/log /var/tmp /var/roothome /var/opt /var/srv /var/mnt /var/spool /var/cache /var/usrlocal
chmod 0755 /var/home
chmod 1777 /var/tmp
chmod 0700 /var/roothome
if [ ! -f /etc/fstab ] || ! grep -q "subvol=root" /etc/fstab || ! grep -q "subvol=var" /etc/fstab || ! grep -q "subvol=home" /etc/fstab; then
    echo "FATAL: Expected Btrfs subvolume mounts (root, var, home) missing from /etc/fstab" >&2
    exit 1
fi
if command -v systemd-machine-id-setup >/dev/null 2>&1; then
    systemd-machine-id-setup
fi

echo "KUSHAGRA_POST: staging bootc kernel and initramfs into /boot"
KVER=""
for d in $(ls -1d /usr/lib/modules/*/ 2>/dev/null | sort -Vr || true); do
    [ -f "${d}vmlinuz" ] && [ -f "${d}initramfs.img" ] || continue
    KVER="$(basename "${d%/}")"
    break
done
if [ -z "$KVER" ]; then
    for d in $(ls -1d /usr/lib/modules/*/ 2>/dev/null | sort -Vr || true); do
        [ -f "${d}vmlinuz" ] || continue
        KVER="$(basename "${d%/}")"
        break
    done
fi
if [ -z "$KVER" ]; then
    echo "FATAL: No kernel vmlinuz found under /usr/lib/modules" >&2
    exit 1
fi
mkdir -p /boot
cp -f "/usr/lib/modules/${KVER}/vmlinuz" "/boot/vmlinuz-${KVER}"
if [ -f "/usr/lib/modules/${KVER}/initramfs.img" ]; then
    cp -f "/usr/lib/modules/${KVER}/initramfs.img" "/boot/initramfs-${KVER}.img"
else
    dracut -N --force "/boot/initramfs-${KVER}.img" "${KVER}"
fi

echo "KUSHAGRA_POST: staging Fedora UEFI binaries (dual-boot safe)"
mkdir -p /boot/efi/EFI/fedora /boot/efi/EFI/BOOT
for efi_src in /usr/lib/efi/shim/*/EFI/fedora/* /usr/lib/efi/grub2/*/EFI/fedora/*; do
    if [ -e "$efi_src" ]; then
        cp -rfL "$efi_src" /boot/efi/EFI/fedora/
    fi
done
if [ ! -f /boot/efi/EFI/fedora/grubx64.efi ]; then
    for g_src in $(find /usr/lib/efi -type f -name 'grubx64.efi' 2>/dev/null || true); do
        cp -fL "$g_src" /boot/efi/EFI/fedora/grubx64.efi
        break
    done
fi
if [ ! -f /boot/efi/EFI/fedora/grubx64.efi ]; then
    echo "FATAL: Missing grubx64.efi after staging EFI binaries" >&2
    exit 1
fi
if [ ! -e /boot/efi/EFI/BOOT/BOOTX64.EFI ]; then
    if [ -f /boot/efi/EFI/fedora/shimx64.efi ]; then
        cp -fL /boot/efi/EFI/fedora/shimx64.efi /boot/efi/EFI/BOOT/BOOTX64.EFI
    else
        for b_src in /usr/lib/efi/shim/*/EFI/BOOT/BOOTX64.EFI; do
            if [ -f "$b_src" ]; then
                cp -fL "$b_src" /boot/efi/EFI/BOOT/BOOTX64.EFI
                break
            fi
        done
    fi
    if [ -f /boot/efi/EFI/fedora/grubx64.efi ] && [ ! -e /boot/efi/EFI/BOOT/grubx64.efi ]; then
        cp -fL /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/grubx64.efi
    fi
fi

echo "KUSHAGRA_POST: generating GRUB2 boot config and grubenv"
ROOT_UUID="$(findmnt -n -o UUID / | head -n1 || true)"
BOOT_UUID="$(findmnt -n -o UUID /boot 2>/dev/null | head -n1 || true)"
EFI_UUID="$(findmnt -n -o UUID /boot/efi 2>/dev/null | head -n1 || true)"
if [ -z "$ROOT_UUID" ]; then
    echo "FATAL: Could not resolve root filesystem UUID" >&2
    exit 1
fi
if [ -n "$BOOT_UUID" ]; then
    GRUB_BOOT_UUID="$BOOT_UUID"
    BOOT_PREFIX=""
else
    GRUB_BOOT_UUID="$ROOT_UUID"
    BOOT_PREFIX="/root/boot"
fi

cat <<EOF > /boot/efi/EFI/fedora/grub.cfg
search --no-floppy --fs-uuid --set=dev ${GRUB_BOOT_UUID}
set prefix=(\$dev)${BOOT_PREFIX}/grub2
export prefix
configfile \$prefix/grub.cfg
EOF

mkdir -p /boot/grub2
rm -f /boot/grub2/grubenv
grub2-editenv /boot/grub2/grubenv create
cat <<EOF > /boot/grub2/grub.cfg
set default="0"
set timeout=5
set timeout_style=menu
terminal_output console

menuentry "Kushagra OS 44 (${KVER})" --class fedora --class gnu-linux --class gnu --class os {
    search --no-floppy --fs-uuid --set=root ${GRUB_BOOT_UUID}
    linux ${BOOT_PREFIX}/vmlinuz-${KVER} root=UUID=${ROOT_UUID} rootfstype=btrfs rootflags=subvol=root rw quiet splash
    initrd ${BOOT_PREFIX}/initramfs-${KVER}.img
}
EOF
if [ -f /boot/efi/EFI/Microsoft/Boot/bootmgfw.efi ] && [ -n "$EFI_UUID" ]; then
    cat <<EOF >> /boot/grub2/grub.cfg

menuentry "Windows Boot Manager" --class windows --class os {
    search --no-floppy --fs-uuid --set=root ${EFI_UUID}
    chainloader /EFI/Microsoft/Boot/bootmgfw.efi
}
EOF
fi

echo "KUSHAGRA_POST: registering UEFI NVRAM entry"
EFI_DEV="$(findmnt -n -o SOURCE /boot/efi 2>/dev/null | head -n1 | sed 's/\[.*\]//' || true)"
if [ -n "$EFI_DEV" ] && command -v efibootmgr >/dev/null 2>&1; then
    PK_RAW="$(lsblk -no PKNAME "$EFI_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]' || true)"
    PK=""
    if [ -n "$PK_RAW" ]; then
        PK="$(basename "$PK_RAW")"
    fi
    PARTN="$(lsblk -no PARTN "$EFI_DEV" 2>/dev/null | head -n1 | tr -d '[:space:]' || true)"
    if [ -z "$PARTN" ] && [ -r "/sys/class/block/$(basename "$EFI_DEV")/partition" ]; then
        PARTN="$(cat "/sys/class/block/$(basename "$EFI_DEV")/partition" 2>/dev/null | tr -d '[:space:]' || true)"
    fi
    if [ -n "$PK" ] && [ -n "$PARTN" ]; then
        EFI_LOADER='\EFI\fedora\shimx64.efi'
        if [ ! -f /boot/efi/EFI/fedora/shimx64.efi ] && [ -f /boot/efi/EFI/fedora/grubx64.efi ]; then
            EFI_LOADER='\EFI\fedora\grubx64.efi'
        fi
        efibootmgr -c -d "/dev/${PK}" -p "${PARTN}" -L "Kushagra OS" -l "${EFI_LOADER}" || true
    fi
fi

echo "KUSHAGRA_POST: arming Stage 2 OOBE"
rm -f /etc/kushagra-oobe-done
mkdir -p /var/lib
touch /var/lib/kushagra-oobe-pending /etc/plasma-setup-done
chmod 0644 /var/lib/kushagra-oobe-pending /etc/plasma-setup-done
systemctl disable plasma-setup.service 2>/dev/null || true
systemctl enable kushagra-oobe.service 2>/dev/null || true
restorecon -RF /etc /boot /var/lib 2>/dev/null || true
%end"""

    lines = [
        "# Generated automatically by Kushagra OS K-Installer (v0.2.1)",
        "cmdline",
        'liveimg --url="file:///run/initramfs/live/LiveOS/squashfs.img"',
        "keyboard --xlayouts='in'",
        "lang en_IN.UTF-8",
        "timezone Asia/Kolkata --utc",
        "",
        "# Seal root & skip Anaconda account creation so Stage 2 kushagra-setup (OOBE) runs on first boot",
        "rootpw --lock",
        "firstboot --disable",
        'services --enabled="kushagra-oobe.service"',
        "",
        *storage_lines,
        "",
        post_block,
        "",
    ]
    return "\n".join(lines)
