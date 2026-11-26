#!/usr/bin/env python3
"""Deterministic Kickstart generator for Kushagra OS Stage 1 K-Installer."""

import re

SAFE_DEV_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _check_kname(name: str, role: str) -> str:
    clean = (name or "").strip()
    if not clean or not SAFE_DEV_RE.match(clean):
        raise ValueError(f"Unsafe kernel device name for {role}: {name!r}")
    return clean


def build_kickstart(target: dict) -> str:
    """Build a non-interactive Fedora 44 Kickstart preserving neighbors & enabling Stage 2 OOBE."""
    kind = target.get("kind")
    disk_kname = _check_kname(target.get("diskKname", ""), "disk")
    esp_kname = (target.get("espKname") or "").strip()
    if esp_kname:
        esp_kname = _check_kname(esp_kname, "esp")

    storage_lines = [
        "# Preserve all existing disks, Windows partitions, and EFI entries",
        "clearpart --none",
        f"bootloader --location=mbr --boot-drive={disk_kname}",
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
        "btrfs /home --subvol --name=home kushagra_os",
    ])

    lines = [
        "# Generated automatically by Kushagra OS K-Installer (v0.2.0)",
        "cmdline",
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
        "# Reboot action allows Anaconda cmdline progress spoke to exit cleanly while LIVE_OS can_reboot=False keeps UI open",
        "reboot",
        "",
        "%post --erroronfail",
        "# Strip any transient LiveCD session artifacts copied from overlay",
        "rm -f /etc/sudoers.d/90-liveuser",
        "rm -rf /home/liveuser",
        "if [ -f /etc/plasmalogin.conf ]; then",
        "    sed -i -E 's/^User=liveuser$/#User=/; s/^Session=plasma\\.desktop$/#Session=/' /etc/plasmalogin.conf",
        "fi",
        "rm -f /etc/plasmalogin.conf.d/00-kushagra-oobe.conf /etc/plasmalogin.conf.d/10-user-autologin.conf",
        "",
        "# Guarantee Stage 2 kushagra-setup OOBE activation on first reboot",
        "rm -f /etc/kushagra-oobe-done",
        "mkdir -p /var/lib",
        "touch /var/lib/kushagra-oobe-pending /etc/plasma-setup-done",
        "chmod 0644 /var/lib/kushagra-oobe-pending",
        "systemctl disable plasma-setup.service 2>/dev/null || true",
        "systemctl enable kushagra-oobe.service 2>/dev/null || true",
        "%end",
        "",
    ]
    return "\n".join(lines)
