#!/usr/bin/env python3
"""Offline native bootc deployment engine for Kushagra OS K-Installer (v0.5.0)."""

from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import select
import shutil
import stat
import subprocess
import time
from typing import Callable

OCI_SOURCE_DIR = "/run/initramfs/live/kushagra-oci"
DEFAULT_TARGET_IMGREF = "ghcr.io/sgunjan2302-hash/kushagra-os:44"
SYSROOT_MNT = "/mnt/sysroot"
INSTALLED_MNT = "/mnt/installed"
RUN_DIR = "/run/kushagra-installer"
EFI_BACKUP_DIR = os.path.join(RUN_DIR, "efi-microsoft-backup")
DUALBOOT_GRUB_BIN = "/usr/libexec/kushagra-dualboot-grub"

MIB = 1024 * 1024
ESP_SIZE_MIB = 512
BOOT_SIZE_MIB = 1024
MIN_BTRFS_BYTES = 16 * 1024 * 1024 * 1024  # 16 GiB minimum root payload

CRITICAL_HOST_MOUNTS = {
    "/",
    "/boot",
    "/boot/efi",
    "/var",
    "/home",
    "/sysroot",
    "/usr",
}

SILENT_OEM_KARGS = [
    "quiet",
    "splash",
    "rhgb",
    "loglevel=3",
    "systemd.show_status=false",
    "rd.systemd.show_status=auto",
    "rd.udev.log_level=3",
    "udev.log_priority=3",
    "vt.global_cursor_default=0",
]

ProgressCallback = Callable[[int, str, list[str] | None], None]


def _emit(cb: ProgressCallback | None, percent: int, stage: str, logs: list[str] | None = None) -> None:
    if cb is not None:
        cb(percent, stage, logs or [])


def _run_checked(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if res.returncode != 0:
        detail = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
        raise RuntimeError(f"Command {' '.join(cmd)} failed (rc={res.returncode}): {detail}")
    return res


def _is_mounted(mountpoint: str) -> bool:
    if os.path.ismount(mountpoint):
        return True
    if shutil.which("findmnt"):
        res = subprocess.run(["findmnt", "-n", "-M", mountpoint], capture_output=True, text=True, check=False)
        return res.returncode == 0 and bool(res.stdout.strip())
    return False


def _flush_fs() -> None:
    if hasattr(os, "sync"):
        os.sync()
    elif shutil.which("sync"):
        subprocess.run(["sync"], capture_output=True, check=False)


def _unmount_recursive(mountpoint: str) -> None:
    if not os.path.exists(mountpoint):
        return
    if not _is_mounted(mountpoint):
        return
    _flush_fs()
    last_err = ""
    for attempt in range(4):
        if shutil.which("udevadm"):
            subprocess.run(["udevadm", "settle", "--timeout=5"], capture_output=True, check=False)
        res = subprocess.run(["umount", "-R", mountpoint], capture_output=True, text=True, check=False)
        if res.returncode == 0 or not _is_mounted(mountpoint):
            return
        last_err = (res.stderr or res.stdout or f"exit {res.returncode}").strip()
        if attempt < 3:
            time.sleep(0.5)
    raise RuntimeError(f"Failed to unmount {mountpoint}: {last_err}")


def _is_block_device(path: str) -> bool:
    if not path:
        return False
    try:
        st = os.stat(path)
        return stat.S_ISBLK(st.st_mode)
    except OSError:
        return False


def _detect_target_imgref() -> str:
    """Resolve matching Kushagra OS GHCR target ref from /etc/os-release."""
    os_release_path = "/etc/os-release"
    if os.path.isfile(os_release_path):
        try:
            text = open(os_release_path, "r", encoding="utf-8", errors="replace").read()
            match = re.search(r'^PRETTY_NAME=(?:"([^"]*)"|([^\n]*))', text, re.MULTILINE)
            if match:
                pretty = (match.group(1) or match.group(2) or "").strip()
                if "DX NVIDIA" in pretty:
                    return "ghcr.io/sgunjan2302-hash/kushagra-os-dx-nvidia:44"
                if "NVIDIA" in pretty:
                    return "ghcr.io/sgunjan2302-hash/kushagra-os-nvidia:44"
                if re.search(r"\bDX\b", pretty):
                    return "ghcr.io/sgunjan2302-hash/kushagra-os-dx:44"
        except OSError:
            pass
    return DEFAULT_TARGET_IMGREF


def _verify_offline_oci_payload() -> None:
    """Fail loudly before any disk mutation if offline OCI payload is absent or invalid."""
    if not os.path.isdir(OCI_SOURCE_DIR):
        raise RuntimeError(
            f"Offline OCI image payload directory not found: {OCI_SOURCE_DIR}. "
            "Cannot proceed with installation; zero disk changes were made."
        )
    layout_file = os.path.join(OCI_SOURCE_DIR, "oci-layout")
    index_file = os.path.join(OCI_SOURCE_DIR, "index.json")
    if not os.path.isfile(layout_file) or not os.path.isfile(index_file):
        raise RuntimeError(
            f"Incomplete offline OCI payload at {OCI_SOURCE_DIR} "
            "(missing required oci-layout or index.json). Zero disk changes were made."
        )
    try:
        with open(index_file, "r", encoding="utf-8") as fp:
            index_data = json.load(fp)
    except Exception as exc:
        raise RuntimeError(f"Corrupt OCI index.json at {index_file}: {exc}") from exc

    manifests = index_data.get("manifests")
    if not isinstance(manifests, list) or not manifests:
        raise RuntimeError(f"Empty or invalid OCI manifests in {index_file}.")


def _preflight_checks(target: dict, emit: ProgressCallback | None) -> None:
    """Verify privileges, OCI payload, target safety, mount cleanliness, and tools."""
    if os.geteuid() != 0:
        raise PermissionError("bootc_deploy requires root privileges.")

    _emit(emit, 5, "Verifying offline OCI payload & installer preflight checks...", [
        f"Checking offline OCI directory {OCI_SOURCE_DIR}...",
    ])
    _verify_offline_oci_payload()

    if not isinstance(target, dict):
        raise ValueError("Invalid installation target payload.")
    if target.get("isLive") or target.get("isWindows") or target.get("isEsp"):
        raise ValueError(f"Refused: protected target {target.get('id')!r} cannot be modified.")
    if target.get("selectable") is False:
        raise ValueError(f"Refused: target {target.get('id')!r} is marked non-selectable.")

    kind = target.get("kind")
    if kind not in ("unallocated", "partition"):
        raise ValueError(f"Unsupported target kind: {kind!r}")

    disk_path = str(target.get("diskPath") or "").strip()
    if not _is_block_device(disk_path):
        raise ValueError(f"Target disk device is missing or not a block device: {disk_path!r}")

    esp_path = str(target.get("espPath") or "").strip()
    if esp_path and not _is_block_device(esp_path):
        raise ValueError(f"Preserved EFI partition is missing or not a block device: {esp_path!r}")

    if kind == "partition":
        part_path = str(target.get("partPath") or "").strip()
        if not _is_block_device(part_path):
            raise ValueError(f"Target partition is missing or not a block device: {part_path!r}")
        if not esp_path:
            raise ValueError("Partition install mode requires an existing EFI System Partition.")
        if os.path.realpath(part_path) == os.path.realpath(esp_path):
            raise ValueError("Refused: target partition cannot be the EFI System Partition.")
    else:
        raw_start = target.get("startBytes") if target.get("startBytes") is not None else target.get("gapStartBytes")
        raw_size = target.get("sizeBytes")
        if raw_start is None or raw_size is None:
            raise ValueError("Unallocated target missing required startBytes/sizeBytes bounds.")
        if int(raw_start) < 0 or int(raw_size) < 18 * 1024 * 1024 * 1024:
            raise ValueError(f"Unallocated gap too small or invalid bounds: start={raw_start}, size={raw_size}.")

    required_bins = [
        "parted",
        "mkfs.btrfs",
        "btrfs",
        "blkid",
        "udevadm",
        "podman",
        "findmnt",
        "mount",
        "umount",
        "systemd-machine-id-setup",
        "bootc",
    ]
    if kind == "unallocated":
        required_bins.append("mkfs.ext4")
        if not esp_path:
            required_bins.append("mkfs.fat")

    missing = [b for b in required_bins if not shutil.which(b)]
    if not os.access(DUALBOOT_GRUB_BIN, os.X_OK):
        missing.append(DUALBOOT_GRUB_BIN)
    if missing:
        raise RuntimeError(f"Missing required deployment tool(s): {', '.join(missing)}")

    for mnt in (INSTALLED_MNT, SYSROOT_MNT):
        if _is_mounted(mnt):
            raise RuntimeError(f"Mountpoint {mnt} is already mounted; aborting for safety.")

    _emit(emit, 7, "Offline OCI payload & disk safety preflight passed.", [
        f"Verified {OCI_SOURCE_DIR}/oci-layout and {OCI_SOURCE_DIR}/index.json",
    ])


def _list_parted_state(disk_path: str) -> tuple[list[dict[str, int]], set[int]]:
    """Query parted in bytes for free regions and active partition numbers."""
    res = _run_checked(["parted", "-ms", disk_path, "unit", "B", "print", "free"])
    free_gaps: list[dict[str, int]] = []
    part_nums: set[int] = set()
    for raw in res.stdout.splitlines():
        line = raw.strip().rstrip(";")
        parts = line.split(":")
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        if parts[4] == "free":
            try:
                start_b = int(parts[1].rstrip("B"))
                end_b = int(parts[2].rstrip("B"))
                size_b = int(parts[3].rstrip("B"))
            except ValueError:
                continue
            free_gaps.append({"start": start_b, "end": end_b, "size": size_b})
        else:
            part_nums.add(int(parts[0]))
    return free_gaps, part_nums


def _list_disk_partition_children(disk_path: str) -> list[dict]:
    res = _run_checked(["lsblk", "-J", "-b", "-p", "-o", "PATH,KNAME,PARTN,TYPE", disk_path])
    data = json.loads(res.stdout or "{}")
    children: list[dict] = []
    for dev in data.get("blockdevices", []):
        for child in dev.get("children") or []:
            if child.get("type") == "part":
                children.append(child)
    return children


def _wait_for_partition_node(disk_path: str, part_num: int) -> str:
    """Wait for udev to expose the block device node for GPT partition part_num."""
    if shutil.which("partprobe"):
        subprocess.run(["partprobe", disk_path], capture_output=True, check=False)

    for _ in range(25):
        subprocess.run(["udevadm", "settle", "--timeout=5"], capture_output=True, check=False)
        for child in _list_disk_partition_children(disk_path):
            raw_pn = child.get("partn")
            try:
                if raw_pn is not None and int(raw_pn) == part_num:
                    dev_path = str(child.get("path") or "").strip()
                    if _is_block_device(dev_path):
                        return dev_path
            except (TypeError, ValueError):
                continue
        time.sleep(0.2)

    raise RuntimeError(f"Timed out waiting for partition #{part_num} device node on {disk_path}.")


def _create_gpt_partition(
    disk_path: str,
    part_label: str,
    fs_type: str,
    start_b: int,
    end_b: int,
    set_esp: bool = False,
) -> str:
    """Create a 1 MiB-aligned GPT partition inside [start_b, end_b] and return its device path."""
    if end_b <= start_b:
        raise ValueError(f"Invalid partition range [{start_b}, {end_b}] for {part_label}.")

    _, before_nums = _list_parted_state(disk_path)
    _run_checked([
        "parted", "-s", "-a", "optimal", disk_path, "unit", "B",
        "mkpart", part_label, fs_type, f"{start_b}B", f"{end_b}B",
    ])
    _, after_nums = _list_parted_state(disk_path)
    created = sorted(after_nums - before_nums)
    if len(created) != 1:
        raise RuntimeError(
            f"Expected exactly 1 new partition on {disk_path} for {part_label}, detected {created}."
        )
    part_num = created[0]

    if set_esp:
        _run_checked(["parted", "-s", disk_path, "set", str(part_num), "esp", "on"])

    return _wait_for_partition_node(disk_path, part_num)


def _wipe_signatures(dev_path: str) -> None:
    if shutil.which("wipefs"):
        subprocess.run(["wipefs", "-a", "-f", dev_path], capture_output=True, check=False)


def _ensure_partition_unmounted(dev_path: str, label: str) -> None:
    res = subprocess.run(
        ["findmnt", "-n", "-o", "TARGET", "--source", dev_path],
        capture_output=True, text=True, check=False,
    )
    if res.returncode != 0 or not res.stdout.strip():
        return
    for mp in [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]:
        if mp in CRITICAL_HOST_MOUNTS or mp.startswith("/run/initramfs"):
            raise RuntimeError(f"Refused: {label} ({dev_path}) is mounted on critical path {mp}.")
        _run_checked(["umount", mp])


def _prepare_storage(target: dict, emit: ProgressCallback | None) -> tuple[str, str | None, str]:
    """Partition/format strictly the selected target and return (root_dev, boot_dev, esp_dev)."""
    kind = target["kind"]
    disk_path = str(target["diskPath"]).strip()
    existing_esp = str(target.get("espPath") or "").strip()

    if kind == "partition":
        root_dev = str(target["partPath"]).strip()
        esp_dev = existing_esp
        _ensure_partition_unmounted(root_dev, "target partition")
        _ensure_partition_unmounted(esp_dev, "preserved EFI partition")

        _emit(emit, 12, f"Formatting target partition {root_dev} as Btrfs...", [
            f"Partition mode: formatting ONLY {root_dev} (preserving {esp_dev} and all neighboring partitions).",
        ])
        _wipe_signatures(root_dev)
        _run_checked(["mkfs.btrfs", "-f", "-L", "kushagra_os", root_dev])
        return root_dev, None, esp_dev

    # Unallocated gap mode
    needs_init_gpt = bool(target.get("needsInitGpt"))
    if needs_init_gpt:
        existing_parts = _list_disk_partition_children(disk_path)
        if existing_parts:
            raise RuntimeError(
                f"Refused to initialize GPT on {disk_path}: existing partition(s) detected."
            )
        _emit(emit, 10, f"Initializing GPT partition table on blank disk {disk_path}...", [
            f"Running parted mklabel gpt on blank disk {disk_path}",
        ])
        _run_checked(["parted", "-s", disk_path, "mklabel", "gpt"])
        subprocess.run(["udevadm", "settle", "--timeout=10"], capture_output=True, check=False)

    free_gaps, _ = _list_parted_state(disk_path)
    if not free_gaps:
        raise RuntimeError(f"No unallocated free regions found on {disk_path}.")

    if needs_init_gpt:
        gap = max(free_gaps, key=lambda g: g["size"])
        bound_start = gap["start"]
        bound_end = gap["end"]
    else:
        raw_start = target.get("startBytes") if target.get("startBytes") is not None else target.get("gapStartBytes")
        req_start = int(raw_start)
        req_end = req_start + int(target["sizeBytes"]) - 1

        matching = [
            g for g in free_gaps
            if g["start"] <= req_end and g["end"] >= req_start and abs(g["start"] - req_start) <= MIB
        ]
        if not matching:
            matching = [
                g for g in free_gaps
                if g["start"] <= req_start and g["end"] >= req_end
            ]
        if not matching:
            raise RuntimeError(
                f"Requested unallocated region [{req_start}, {req_end}] on {disk_path} "
                "no longer matches live partition table; aborting without changes."
            )
        gap = max(matching, key=lambda g: g["size"])
        bound_start = max(gap["start"], req_start)
        bound_end = min(gap["end"], req_end)

    # Align strictly inside [bound_start, bound_end] on 1 MiB boundaries so neighbors are never overlapped
    alloc_start = ((bound_start + MIB - 1) // MIB) * MIB
    alloc_end_excl = ((bound_end + 1) // MIB) * MIB
    if alloc_start < gap["start"] or (alloc_end_excl - 1) > gap["end"] or alloc_end_excl <= alloc_start:
        raise RuntimeError(
            f"Aligned bounds [{alloc_start}, {alloc_end_excl - 1}] exceed live free gap "
            f"[{gap['start']}, {gap['end']}] on {disk_path}."
        )

    needed_mib = BOOT_SIZE_MIB + (0 if existing_esp else ESP_SIZE_MIB)
    available_bytes = alloc_end_excl - alloc_start
    if available_bytes - (needed_mib * MIB) < MIN_BTRFS_BYTES:
        raise RuntimeError(
            f"Aligned free space ({available_bytes // (1024 ** 3)} GiB) is insufficient "
            "for EFI/boot + 16 GiB minimum Btrfs root."
        )

    _emit(emit, 12, f"Creating Kushagra OS partitions inside unallocated space on {disk_path}...", [
        f"Exact gap bounds: {alloc_start}B..{alloc_end_excl - 1}B ({available_bytes // MIB} MiB)",
    ])

    cursor = alloc_start
    if not existing_esp:
        esp_end = cursor + (ESP_SIZE_MIB * MIB) - 1
        esp_dev = _create_gpt_partition(disk_path, "EFI", "fat32", cursor, esp_end, set_esp=True)
        cursor = esp_end + 1
        _wipe_signatures(esp_dev)
        _run_checked(["mkfs.fat", "-F32", esp_dev])
        _emit(emit, 14, f"Created 512 MiB FAT32 EFI partition ({esp_dev})...", [
            f"Formatted new EFI System Partition {esp_dev} as FAT32",
        ])
    else:
        esp_dev = existing_esp
        _ensure_partition_unmounted(esp_dev, "preserved EFI partition")
        _emit(emit, 14, f"Preserving existing EFI System Partition ({esp_dev})...", [
            f"Preserving existing ESP {esp_dev} (--noformat)",
        ])

    boot_end = cursor + (BOOT_SIZE_MIB * MIB) - 1
    boot_dev = _create_gpt_partition(disk_path, "kushagra_boot", "ext4", cursor, boot_end)
    cursor = boot_end + 1
    _wipe_signatures(boot_dev)
    _run_checked(["mkfs.ext4", "-F", "-L", "kushagra_boot", boot_dev])
    _emit(emit, 16, f"Created 1 GiB ext4 /boot partition ({boot_dev})...", [
        f"Formatted {boot_dev} as ext4 (kushagra_boot)",
    ])

    btrfs_end = alloc_end_excl - 1
    root_dev = _create_gpt_partition(disk_path, "kushagra_os", "btrfs", cursor, btrfs_end)
    _wipe_signatures(root_dev)
    _run_checked(["mkfs.btrfs", "-f", "-L", "kushagra_os", root_dev])
    _emit(emit, 18, f"Formatted Btrfs root partition ({root_dev})...", [
        f"Formatted {root_dev} as Btrfs (kushagra_os)",
    ])

    return root_dev, boot_dev, esp_dev


def _resolve_uuid(dev_path: str) -> str:
    subprocess.run(["udevadm", "settle", "--timeout=10"], capture_output=True, check=False)
    for _ in range(10):
        for cmd in (["blkid", "-s", "UUID", "-o", "value", dev_path], ["blkid", "-p", "-s", "UUID", "-o", "value", dev_path]):
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            uuid_val = res.stdout.strip().splitlines()[0].strip() if res.stdout.strip() else ""
            if uuid_val:
                return uuid_val
        time.sleep(0.3)
    raise RuntimeError(f"Could not resolve filesystem UUID for {dev_path} via blkid.")


def _find_microsoft_efi_dir(efi_mount: str) -> str | None:
    efi_parent = os.path.join(efi_mount, "EFI")
    if not os.path.isdir(efi_parent):
        return None
    exact = os.path.join(efi_parent, "Microsoft")
    if os.path.isdir(exact):
        return exact
    try:
        for entry in os.listdir(efi_parent):
            if entry.lower() == "microsoft":
                cand = os.path.join(efi_parent, entry)
                if os.path.isdir(cand):
                    return cand
    except OSError:
        return None
    return None


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _backup_windows_efi(ms_dir: str, backup_dir: str) -> dict[str, str]:
    """Copy every file in EFI/Microsoft to RAM backup_dir and return {rel_path: sha256}."""
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    os.makedirs(backup_dir, mode=0o700, exist_ok=True)

    manifest: dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(ms_dir, followlinks=False):
        rel_dir = os.path.relpath(dirpath, ms_dir)
        dst_dir = backup_dir if rel_dir == "." else os.path.join(backup_dir, rel_dir)
        os.makedirs(dst_dir, exist_ok=True)
        for name in sorted(filenames):
            src_file = os.path.join(dirpath, name)
            if os.path.islink(src_file) or not os.path.isfile(src_file):
                continue
            rel_file = name if rel_dir == "." else os.path.join(rel_dir, name)
            dst_file = os.path.join(backup_dir, rel_file)
            shutil.copy2(src_file, dst_file)
            manifest[rel_file] = _sha256_file(src_file)
    return manifest


def _verify_or_restore_windows_efi(
    ms_dir: str,
    backup_dir: str,
    manifest: dict[str, str],
    emit: ProgressCallback | None,
) -> None:
    """Verify byte-identical EFI/Microsoft SHA256 digests; restore from RAM if altered."""
    if not manifest:
        return

    mismatches: list[str] = []
    for rel_file, expected_hash in manifest.items():
        live_file = os.path.join(ms_dir, rel_file)
        if not os.path.isfile(live_file) or _sha256_file(live_file) != expected_hash:
            mismatches.append(rel_file)

    if not mismatches:
        _emit(emit, 97, "Verified Windows EFI (Microsoft) byte-identical via SHA256...", [
            f"[PASS] Windows EFI intact: {len(manifest)} file(s) matched SHA256 digest.",
        ])
        return

    _emit(emit, 96, "Restoring Windows EFI files from RAM backup after mismatch...", [
        f"[WARN] Detected {len(mismatches)} modified/missing Windows EFI file(s); restoring from RAM backup...",
    ])
    for rel_file in manifest:
        src_file = os.path.join(backup_dir, rel_file)
        dst_file = os.path.join(ms_dir, rel_file)
        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
        shutil.copy2(src_file, dst_file)
    _flush_fs()

    still_bad = [
        rel_file for rel_file, expected_hash in manifest.items()
        if not os.path.isfile(os.path.join(ms_dir, rel_file))
        or _sha256_file(os.path.join(ms_dir, rel_file)) != expected_hash
    ]
    if still_bad:
        raise RuntimeError(
            f"Windows EFI SHA256 verification failed after RAM restore for: {', '.join(still_bad[:10])}"
        )

    _emit(emit, 97, "Windows EFI restored & verified byte-identical via SHA256.", [
        f"[PASS] Windows EFI restored cleanly: {len(manifest)} file(s) verified.",
    ])


def _run_bootc_to_filesystem(
    root_uuid: str,
    boot_uuid: str | None,
    target_imgref: str,
    emit: ProgressCallback | None,
) -> None:
    """Run bootc install to-filesystem inside unconfined_t via podman without --disable-selinux."""
    subprocess.run(["mount", "--make-rshared", SYSROOT_MNT], capture_output=True, check=False)

    cmd = [
        "podman",
        "run",
        "--rm",
        "--privileged",
        "--pid=host",
        "--ipc=host",
        "-v", "/dev:/dev",
        "-v", f"{SYSROOT_MNT}:{SYSROOT_MNT}:rshared",
        "-v", f"{OCI_SOURCE_DIR}:{OCI_SOURCE_DIR}:ro",
        "--security-opt", "label=type:unconfined_t",
        "--rootfs", "/:O",
        "/usr/bin/bootc",
        "install",
        "to-filesystem",
        f"--source-imgref=oci:{OCI_SOURCE_DIR}",
        "--target-transport=registry",
        f"--target-imgref={target_imgref}",
        "--enforce-container-sigpolicy",
        "--skip-fetch-check",
        f"--root-mount-spec=UUID={root_uuid}",
    ]
    if boot_uuid:
        cmd.append(f"--boot-mount-spec=UUID={boot_uuid}")

    cmd.extend([
        "--bootloader=grub",
        "--stateroot=default",
        "--skip-finalize",
        "--karg=rootflags=compress=zstd:1",
        *[f"--karg={arg}" for arg in SILENT_OEM_KARGS],
        SYSROOT_MNT,
    ])

    _emit(emit, 30, "Deploying offline Kushagra OS bootc image to Btrfs...", [
        f"Running bootc install to-filesystem (target {target_imgref})...",
    ])

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )
    assert proc.stdout is not None
    fd = proc.stdout.fileno()
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    pending_text = ""

    percent = 30
    last_heartbeat = time.monotonic()
    last_creep = last_heartbeat
    tail_lines: list[str] = []

    def _consume_text(text_chunk: str, flush_tail: bool = False) -> list[str]:
        nonlocal pending_text
        pending_text += text_chunk.replace("\r", "\n")
        parts = pending_text.split("\n")
        if flush_tail:
            pending_text = ""
        else:
            pending_text = parts.pop()
        return [p.strip() for p in parts if p.strip()]

    eof_reached = False
    while True:
        new_lines: list[str] = []
        if not eof_reached:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if ready:
                while True:
                    chunk = os.read(fd, 8192)
                    if not chunk:
                        eof_reached = True
                        break
                    new_lines.extend(_consume_text(decoder.decode(chunk, final=False)))
                    if not select.select([fd], [], [], 0)[0]:
                        break
        else:
            time.sleep(0.2)

        now = time.monotonic()
        if new_lines:
            tail_lines.extend(new_lines)
            tail_lines = tail_lines[-50:]
            if percent < 78:
                percent = min(78, percent + 1)
                last_creep = now
            _emit(emit, percent, "Deploying offline Kushagra OS bootc image...", new_lines[-30:])
            last_heartbeat = now
        elif now - last_heartbeat >= 2.0:
            if percent < 78 and (now - last_creep >= 6.0):
                percent += 1
                last_creep = now
            _emit(emit, percent, "Deploying offline Kushagra OS bootc image...", [])
            last_heartbeat = now

        ret = proc.poll()
        if ret is not None:
            while not eof_reached:
                chunk = os.read(fd, 8192)
                if not chunk:
                    eof_reached = True
                    break
                new_lines = _consume_text(decoder.decode(chunk, final=False))
                if new_lines:
                    tail_lines.extend(new_lines)
                    tail_lines = tail_lines[-50:]
                    _emit(emit, percent, "Deploying offline Kushagra OS bootc image...", new_lines[-30:])
            rem_lines = _consume_text(decoder.decode(b"", final=True), flush_tail=True)
            if rem_lines:
                tail_lines.extend(rem_lines)
                tail_lines = tail_lines[-50:]
                _emit(emit, percent, "Deploying offline Kushagra OS bootc image...", rem_lines[-30:])
            break

    if ret != 0:
        detail = tail_lines[-1] if tail_lines else f"exit code {ret}"
        raise RuntimeError(f"bootc install to-filesystem failed (rc={ret}): {detail}")

    _emit(emit, 80, "Offline bootc image staged to disk.", [
        "bootc install to-filesystem completed cleanly.",
    ])


def _is_nonempty_flatpak_install_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    for sub in ("app", "runtime"):
        sub_dir = os.path.join(path, sub)
        if os.path.isdir(sub_dir):
            try:
                if any(True for _ in os.scandir(sub_dir)):
                    return True
            except OSError:
                pass
    heads_dir = os.path.join(path, "repo", "refs", "heads")
    if os.path.isdir(heads_dir):
        for _dp, _dn, fns in os.walk(heads_dir):
            if fns:
                return True
    return False


def _find_ostree_refs(repo_dir: str) -> list[str]:
    heads_dir = os.path.join(repo_dir, "refs", "heads")
    refs: list[str] = []
    if not os.path.isdir(heads_dir):
        return refs
    for dp, _dn, fns in os.walk(heads_dir):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, heads_dir).replace(os.sep, "/")
            refs.append(rel)
    return refs


def _sync_offline_flatpaks(installed_root: str, emit: ProgressCallback | None) -> None:
    """Sync offline Flatpak repo cleanly if present and non-empty; never fail offline installs."""
    dst_flatpak = os.path.join(installed_root, "var", "lib", "flatpak")

    try:
        for cand in ("/run/initramfs/live/flatpak", "/var/lib/flatpak"):
            if _is_nonempty_flatpak_install_dir(cand):
                os.makedirs(dst_flatpak, mode=0o755, exist_ok=True)
                if shutil.which("rsync"):
                    res = subprocess.run(
                        ["rsync", "-aH", f"{cand}/", f"{dst_flatpak}/"],
                        capture_output=True, text=True, check=False,
                    )
                else:
                    res = subprocess.run(
                        ["cp", "-a", f"{cand}/.", f"{dst_flatpak}/"],
                        capture_output=True, text=True, check=False,
                    )
                if res.returncode == 0:
                    _emit(emit, 88, "Synced offline Flatpak repository...", [
                        f"Synced offline Flatpak installation from {cand} -> {dst_flatpak}",
                    ])
                else:
                    err = (res.stderr or res.stdout or f"rc={res.returncode}").strip()
                    _emit(emit, 88, "Skipping partial offline Flatpak sync...", [
                        f"[WARN] Non-fatal offline Flatpak sync warning ({cand}): {err}",
                    ])
                return

        for repo_cand in ("/run/initramfs/live/flatpak-repo", "/run/initramfs/live/repo"):
            if os.path.isfile(os.path.join(repo_cand, "config")) and os.path.isdir(os.path.join(repo_cand, "objects")):
                refs = _find_ostree_refs(repo_cand)
                if not refs:
                    continue
                if not shutil.which("ostree"):
                    _emit(emit, 88, "Skipping offline Flatpak repo (ostree unavailable)...", [
                        "[WARN] ostree binary unavailable for standalone offline Flatpak repo sync.",
                    ])
                    return
                dst_repo = os.path.join(dst_flatpak, "repo")
                os.makedirs(dst_repo, mode=0o755, exist_ok=True)
                if not os.path.isfile(os.path.join(dst_repo, "config")):
                    subprocess.run(
                        ["ostree", f"--repo={dst_repo}", "init", "--mode=bare-user-only"],
                        capture_output=True, text=True, check=False,
                    )
                res = subprocess.run(
                    ["ostree", f"--repo={dst_repo}", "pull-local", repo_cand, *refs],
                    capture_output=True, text=True, check=False,
                )
                if res.returncode == 0:
                    _emit(emit, 88, "Synced offline Flatpak OSTree repository...", [
                        f"Pulled {len(refs)} offline Flatpak ref(s) from {repo_cand}",
                    ])
                else:
                    err = (res.stderr or res.stdout or f"rc={res.returncode}").strip()
                    _emit(emit, 88, "Skipping partial offline Flatpak pull...", [
                        f"[WARN] Non-fatal ostree pull-local warning ({repo_cand}): {err}",
                    ])
                return

        _emit(emit, 88, "No offline Flatpak repository staged; skipping...", [
            "No non-empty offline Flatpak repo present (online setup runs after first boot).",
        ])
    except Exception as exc:
        _emit(emit, 88, "Skipping offline Flatpak sync (non-fatal)...", [
            f"[WARN] Non-fatal offline Flatpak sync error: {exc}",
        ])


def _safe_remove_tree(installed_root: str, rel_path: str) -> None:
    target = os.path.join(installed_root, rel_path)
    if not os.path.lexists(target):
        return
    if os.path.islink(target):
        os.unlink(target)
        return
    real_root = os.path.realpath(installed_root)
    real_target = os.path.realpath(target)
    if not (real_target == real_root or real_target.startswith(real_root + os.sep)):
        return
    if os.path.isdir(target):
        shutil.rmtree(target)
    else:
        os.unlink(target)


def _strip_livecd_artifacts(installed_root: str) -> None:
    """Remove transient LiveCD liveuser/sudoers/plasmalogin autologin artifacts inside sysroot."""
    sudoers_live = os.path.join(installed_root, "etc", "sudoers.d", "90-liveuser")
    if os.path.lexists(sudoers_live):
        os.unlink(sudoers_live)

    _safe_remove_tree(installed_root, os.path.join("var", "home", "liveuser"))
    home_dir = os.path.join(installed_root, "home")
    if os.path.isdir(home_dir) and not os.path.islink(home_dir):
        _safe_remove_tree(installed_root, os.path.join("home", "liveuser"))

    passwd_path = os.path.join(installed_root, "etc", "passwd")
    if os.path.isfile(passwd_path):
        try:
            with open(passwd_path, "r", encoding="utf-8", errors="replace") as fp:
                has_liveuser = any(line.startswith("liveuser:") for line in fp)
            if has_liveuser and shutil.which("userdel"):
                subprocess.run(
                    ["userdel", "--root", installed_root, "-f", "liveuser"],
                    capture_output=True, check=False,
                )
        except OSError:
            pass

    plasmalogin_conf = os.path.join(installed_root, "etc", "plasmalogin.conf")
    if os.path.isfile(plasmalogin_conf):
        try:
            orig = open(plasmalogin_conf, "r", encoding="utf-8", errors="replace").read()
            updated = re.sub(r"^(User=liveuser)$", r"#\1", orig, flags=re.MULTILINE)
            updated = re.sub(r"^(Session=plasma\.desktop)$", r"#\1", updated, flags=re.MULTILINE)
            if updated != orig:
                with open(plasmalogin_conf, "w", encoding="utf-8", newline="\n") as fp:
                    fp.write(updated)
        except OSError:
            pass

    conf_d = os.path.join(installed_root, "etc", "plasmalogin.conf.d")
    if os.path.isdir(conf_d):
        for entry in os.listdir(conf_d):
            full = os.path.join(conf_d, entry)
            if not os.path.isfile(full) and not os.path.islink(full):
                continue
            remove = entry in ("00-kushagra-oobe.conf", "10-user-autologin.conf") or "live" in entry.lower()
            if not remove and os.path.isfile(full):
                try:
                    if "liveuser" in open(full, "r", encoding="utf-8", errors="replace").read():
                        remove = True
                except OSError:
                    pass
            if remove:
                os.unlink(full)


def _configure_installed_sysroot(
    root_uuid: str,
    boot_uuid: str | None,
    esp_uuid: str,
    emit: ProgressCallback | None,
) -> None:
    """Configure /etc/fstab, Stage 2 OOBE, machine-id, LiveCD cleanup, and offline Flatpaks."""
    _emit(emit, 84, "Generating /etc/fstab & arming Stage 2 OOBE inside deployed sysroot...", [
        f"Configuring deployment inside {INSTALLED_MNT}...",
    ])

    etc_dir = os.path.join(INSTALLED_MNT, "etc")
    var_dir = os.path.join(INSTALLED_MNT, "var")
    os.makedirs(etc_dir, mode=0o755, exist_ok=True)
    os.makedirs(var_dir, mode=0o755, exist_ok=True)

    # Ensure mountpoint directories exist inside the deployment
    os.makedirs(os.path.join(INSTALLED_MNT, "boot", "efi"), mode=0o700, exist_ok=True)
    os.makedirs(os.path.join(var_dir, "home"), mode=0o755, exist_ok=True)
    os.makedirs(os.path.join(var_dir, "lib"), mode=0o755, exist_ok=True)
    var_tmp = os.path.join(var_dir, "tmp")
    os.makedirs(var_tmp, mode=0o1777, exist_ok=True)
    os.chmod(var_tmp, 0o1777)
    var_roothome = os.path.join(var_dir, "roothome")
    os.makedirs(var_roothome, mode=0o700, exist_ok=True)
    os.chmod(var_roothome, 0o700)
    for sub in ("log", "opt", "srv", "mnt", "spool", "cache"):
        os.makedirs(os.path.join(var_dir, sub), mode=0o755, exist_ok=True)

    fstab_lines = [
        "# Generated by Kushagra OS K-Installer (offline native bootc deployment)",
        f"UUID={root_uuid} / btrfs compress=zstd:1 0 0",
    ]
    if boot_uuid:
        fstab_lines.append(f"UUID={boot_uuid} /boot ext4 defaults 1 2")
    fstab_lines.extend([
        f"UUID={esp_uuid} /boot/efi vfat umask=0077,shortname=winnt 0 2",
        f"UUID={root_uuid} /var/home btrfs subvol=var/home,compress=zstd:1 0 0",
        "",
    ])
    fstab_path = os.path.join(etc_dir, "fstab")
    with open(fstab_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(fstab_lines))
    os.chmod(fstab_path, 0o644)

    _strip_livecd_artifacts(INSTALLED_MNT)

    # Arm Stage 2 OOBE and suppress upstream KDE plasma-setup
    oobe_done = os.path.join(etc_dir, "kushagra-oobe-done")
    if os.path.lexists(oobe_done):
        os.unlink(oobe_done)

    plasma_done = os.path.join(etc_dir, "plasma-setup-done")
    with open(plasma_done, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("done\n")
    os.chmod(plasma_done, 0o644)

    oobe_pending = os.path.join(var_dir, "lib", "kushagra-oobe-pending")
    with open(oobe_pending, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("pending\n")
    os.chmod(oobe_pending, 0o644)

    _emit(emit, 86, "Initializing machine-id & checking offline Flatpak repo...", [
        "Running systemd-machine-id-setup --root=/mnt/installed",
    ])
    _run_checked(["systemd-machine-id-setup", f"--root={INSTALLED_MNT}"])

    _sync_offline_flatpaks(INSTALLED_MNT, emit)

    file_contexts = os.path.join(etc_dir, "selinux", "targeted", "contexts", "files", "file_contexts")
    if os.path.isfile(file_contexts) and os.access("/usr/sbin/setfiles", os.X_OK):
        relabeled_targets = [
            p for p in (
                fstab_path,
                os.path.join(etc_dir, "machine-id"),
                plasma_done,
                oobe_pending,
                os.path.join(var_dir, "home"),
            )
            if os.path.exists(p)
        ]
        if relabeled_targets:
            subprocess.run(
                ["/usr/sbin/setfiles", "-F", "-r", INSTALLED_MNT, file_contexts, *relabeled_targets],
                capture_output=True, check=False,
            )


def deploy_system(target: dict, emit_progress: ProgressCallback | None = None) -> None:
    """Deploy Kushagra OS offline via native bootc to-filesystem with dual-boot safety."""
    _preflight_checks(target, emit_progress)

    os.makedirs(RUN_DIR, mode=0o755, exist_ok=True)
    target_imgref = _detect_target_imgref()

    root_dev, boot_dev, esp_dev = _prepare_storage(target, emit_progress)

    root_uuid = _resolve_uuid(root_dev)
    boot_uuid = _resolve_uuid(boot_dev) if boot_dev else None
    esp_uuid = _resolve_uuid(esp_dev)

    _emit(emit, 20, "Mounting Btrfs sysroot & creating var/home subvolume...", [
        f"UUIDs: root={root_uuid}, boot={boot_uuid or 'none'}, esp={esp_uuid}",
    ])

    ms_manifest: dict[str, str] = {}
    ms_efi_rel_name = "Microsoft"

    try:
        os.makedirs(SYSROOT_MNT, mode=0o755, exist_ok=True)
        _run_checked(["mount", "-t", "btrfs", "-o", "subvolid=5,compress=zstd:1", root_dev, SYSROOT_MNT])

        sysroot_var = os.path.join(SYSROOT_MNT, "var")
        os.makedirs(sysroot_var, mode=0o755, exist_ok=True)
        _run_checked(["btrfs", "subvolume", "create", os.path.join(sysroot_var, "home")])

        if boot_dev:
            sysroot_boot = os.path.join(SYSROOT_MNT, "boot")
            os.makedirs(sysroot_boot, mode=0o755, exist_ok=True)
            _run_checked(["mount", boot_dev, sysroot_boot])

        sysroot_efi = os.path.join(SYSROOT_MNT, "boot", "efi")
        os.makedirs(sysroot_efi, mode=0o755, exist_ok=True)
        _run_checked(["mount", esp_dev, sysroot_efi])

        ms_efi_dir = _find_microsoft_efi_dir(sysroot_efi)
        if ms_efi_dir:
            ms_efi_rel_name = os.path.basename(ms_efi_dir)
            _emit(emit, 25, "Backing up Windows EFI (EFI/Microsoft) to RAM...", [
                f"Detected {ms_efi_dir}; backing up to RAM and recording SHA256 digests...",
            ])
            ms_manifest = _backup_windows_efi(ms_efi_dir, EFI_BACKUP_DIR)
            _emit(emit, 27, "Windows EFI RAM backup & SHA256 manifest ready.", [
                f"Protected {len(ms_manifest)} Windows EFI file(s) in RAM ({EFI_BACKUP_DIR}).",
            ])

        _run_bootc_to_filesystem(root_uuid, boot_uuid, target_imgref, emit_progress)

        os.makedirs(INSTALLED_MNT, mode=0o755, exist_ok=True)
        _emit(emit, 82, "Mounting deployed ostree root via bootc install mount...", [
            f"Running bootc install mount --sysroot {SYSROOT_MNT} --latest {INSTALLED_MNT}",
        ])
        _run_checked(["bootc", "install", "mount", "--sysroot", SYSROOT_MNT, "--latest", INSTALLED_MNT])

        _configure_installed_sysroot(root_uuid, boot_uuid, esp_uuid, emit_progress)

        _emit(emit, 90, "Unmounting /mnt/installed & writing update-safe GRUB2 custom.cfg...", [
            f"Unmounting {INSTALLED_MNT}",
        ])
        _unmount_recursive(INSTALLED_MNT)

        grub_res = _run_checked([
            DUALBOOT_GRUB_BIN,
            "--grub-dir", os.path.join(SYSROOT_MNT, "boot", "grub2"),
            "--efi-dir", sysroot_efi,
        ])
        grub_logs = [ln.strip() for ln in grub_res.stdout.splitlines() if ln.strip()]
        _emit(emit, 92, "Configured update-safe GRUB2 dual-boot custom.cfg.", grub_logs)

        _emit(emit, 94, "Finalizing bootc deployment...", [
            f"Running bootc install finalize {SYSROOT_MNT}",
        ])
        fin_res = _run_checked(["bootc", "install", "finalize", SYSROOT_MNT])
        fin_logs = [ln.strip() for ln in fin_res.stdout.splitlines() if ln.strip()]
        if fin_logs:
            _emit(emit, 96, "Finalized bootc deployment.", fin_logs[-20:])

        if ms_manifest:
            verify_dir = _find_microsoft_efi_dir(sysroot_efi) or os.path.join(sysroot_efi, "EFI", ms_efi_rel_name)
            _verify_or_restore_windows_efi(verify_dir, EFI_BACKUP_DIR, ms_manifest, emit_progress)

        _emit(emit, 99, "Flushing caches & cleanly unmounting target sysroot...", [
            f"Syncing and unmounting {SYSROOT_MNT}",
        ])
        _unmount_recursive(SYSROOT_MNT)
    finally:
        try:
            _unmount_recursive(INSTALLED_MNT)
        except Exception:
            pass
        try:
            _unmount_recursive(SYSROOT_MNT)
        except Exception:
            pass
        shutil.rmtree(EFI_BACKUP_DIR, ignore_errors=True)
