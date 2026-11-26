#!/usr/bin/env python3
"""Safe block-device, partition, unallocated-gap, and EFI probing for K-Installer."""

import json
import os
import re
import shutil
import subprocess
import tempfile

MIN_TARGET_BYTES = 20 * 1024 * 1024 * 1024  # 20 GiB
MIN_VISUAL_GAP_BYTES = 1 * 1024 * 1024 * 1024  # 1 GiB
MIN_ESP_FREE_MIB = 35

ESP_PARTTYPES = {
    "c12a7328-f81f-11d2-ba4b-00a0c93ec3b3",
    "0xef",
}

WIN_PROTECTED_PARTTYPES = {
    "e3c9e316-0b5c-4db8-817d-f92df00215ae",  # Microsoft Reserved (MSR)
    "de94bba4-06d1-4d40-a16a-bfd50179d6ac",  # Windows Recovery Environment
    "5808c8aa-7e8f-42e0-85d2-e1e90434cfb3",  # LDM Metadata
    "af9b60a0-1431-4f62-bc68-3311714a69ad",  # LDM Data
    "0x7",                                   # MBR NTFS / exFAT
    "0x17",                                  # Hidden NTFS
    "0x27",                                  # Windows RE Hidden
}

WIN_FSTYPES = {"ntfs", "ntfs3", "bitlocker", "refs"}
SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/var", "/home", "/run/initramfs/live", "/sysroot"}


def _human_size(size_bytes: int) -> str:
    gib = size_bytes / (1024 ** 3)
    if gib >= 1.0:
        return f"{gib:.1f} GB"
    mib = size_bytes / (1024 ** 2)
    return f"{mib:.0f} MB"


def _parent_disk_from_source(source: str) -> str:
    """Resolve parent block disk path for a partition/device using lsblk."""
    if not source or not source.startswith("/dev/"):
        return ""
    try:
        res = subprocess.run(
            ["lsblk", "-no", "PKNAME", source],
            capture_output=True, text=True, timeout=5, check=False,
        )
        pkname = res.stdout.strip().splitlines()[0].strip() if res.stdout.strip() else ""
        if pkname:
            return f"/dev/{pkname}"
    except Exception:
        pass
    return re.sub(r"p?\d+$", "", source)


def detect_live_disk_paths() -> set:
    """Identify physical disk(s) backing the booted Live USB / ISO media."""
    live_disks = set()
    for target in ("/run/initramfs/live", "/run/initramfs/isoscan"):
        if not os.path.exists(target):
            continue
        try:
            res = subprocess.run(
                ["findmnt", "-n", "-o", "SOURCE", target],
                capture_output=True, text=True, timeout=5, check=False,
            )
            src = res.stdout.strip().split("[")[0]
            if src.startswith("/dev/loop"):
                los = subprocess.run(
                    ["losetup", "-n", "-O", "BACK-FILE", src],
                    capture_output=True, text=True, timeout=5, check=False,
                )
                back = los.stdout.strip()
                if back.startswith("/dev/"):
                    src = back
            if src.startswith("/dev/"):
                live_disks.add(src)
                parent = _parent_disk_from_source(src)
                if parent:
                    live_disks.add(parent)
        except Exception:
            pass
    return live_disks


def measure_esp_free_mib(part_path: str, mountpoints: list, allow_mount: bool = True):
    """Measure available MiB on an existing FAT32 EFI System Partition safely (read-only)."""
    existing_mp = next((m for m in mountpoints if m), None)
    if existing_mp and os.path.ismount(existing_mp):
        try:
            st = os.statvfs(existing_mp)
            return int((st.f_bavail * st.f_frsize) / (1024 * 1024))
        except Exception:
            return None

    if not allow_mount or os.geteuid() != 0 or not part_path:
        return None

    os.makedirs("/run/kushagra-installer", exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="esp-probe-", dir="/run/kushagra-installer")
    mounted = False
    try:
        res = subprocess.run(
            ["mount", "-o", "ro", part_path, tmp_dir],
            capture_output=True, text=True, timeout=8, check=False,
        )
        if res.returncode == 0:
            mounted = True
            st = os.statvfs(tmp_dir)
            return int((st.f_bavail * st.f_frsize) / (1024 * 1024))
    except Exception:
        return None
    finally:
        if mounted:
            subprocess.run(["umount", tmp_dir], capture_output=True, timeout=8, check=False)
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
    return None


def probe_unallocated_regions(disk_path: str) -> list:
    """Use parted machine-readable output to locate unallocated free regions >= 1 GiB."""
    if not shutil.which("parted"):
        return []
    try:
        res = subprocess.run(
            ["parted", "-ms", disk_path, "unit", "B", "print", "free"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if res.returncode != 0:
            return []
    except Exception:
        return []

    gaps = []
    for raw in res.stdout.splitlines():
        line = raw.strip().rstrip(";")
        parts = line.split(":")
        if len(parts) < 5 or parts[4] != "free":
            continue
        try:
            start_b = int(parts[1].rstrip("B"))
            size_b = int(parts[3].rstrip("B"))
        except ValueError:
            continue
        if size_b >= MIN_VISUAL_GAP_BYTES:
            gaps.append({"startBytes": start_b, "sizeBytes": size_b})
    return gaps


def _normalize_mounts(node: dict) -> list:
    mps = node.get("mountpoints")
    if isinstance(mps, list):
        return [m for m in mps if m]
    mp = node.get("mountpoint")
    return [mp] if mp else []


def _classify_partition(part: dict, disk_path: str, disk_kname: str, is_live_disk: bool, allow_mount: bool) -> dict:
    path = part.get("path") or f"/dev/{part.get('kname', '')}"
    kname = part.get("kname") or os.path.basename(path)
    size_b = int(part.get("size") or 0)
    fstype = (part.get("fstype") or "").strip().lower()
    parttype = (part.get("parttype") or "").strip().lower()
    label = (part.get("label") or "").strip()
    partlabel = (part.get("partlabel") or "").strip()
    combined_label = f"{label} {partlabel}".lower()
    mounts = _normalize_mounts(part)

    is_esp = (parttype in ESP_PARTTYPES) or (fstype == "vfat" and any("efi" in m.lower() for m in mounts))
    is_windows = (
        (fstype in WIN_FSTYPES)
        or (parttype in WIN_PROTECTED_PARTTYPES)
        or any(tok in combined_label for tok in ("windows", "winre", "recovery", "system reserved", "microsoft"))
    )
    is_mounted_sys = any(m in SYSTEM_MOUNTS or m.startswith("/run/initramfs") for m in mounts)

    esp_free_mib = None
    esp_low_space = False
    if is_esp:
        esp_free_mib = measure_esp_free_mib(path, mounts, allow_mount=allow_mount)
        if esp_free_mib is not None and esp_free_mib < MIN_ESP_FREE_MIB:
            esp_low_space = True

    is_too_small = size_b < MIN_TARGET_BYTES
    is_locked = is_live_disk or is_windows or is_esp or is_mounted_sys or bool(mounts)

    if is_live_disk:
        badge = "Live USB (Locked)"
        selectable = False
    elif is_windows:
        badge = "Windows Protected"
        selectable = False
    elif is_esp:
        badge = "EFI System Partition (Preserved)"
        selectable = False
    elif is_mounted_sys or mounts:
        badge = "Mounted System Partition"
        selectable = False
    elif is_too_small:
        badge = "Too Small (< 20 GB)"
        selectable = False
    else:
        badge = "Existing Non-Windows Partition"
        selectable = True

    display_name = label or partlabel or kname
    return {
        "id": f"part:{path}",
        "kind": "partition",
        "diskPath": disk_path,
        "diskKname": disk_kname,
        "partPath": path,
        "partKname": kname,
        "displayName": f"{display_name} ({path})",
        "sizeBytes": size_b,
        "sizeLabel": _human_size(size_b),
        "fstype": fstype or "unformatted",
        "label": label or partlabel,
        "badgeText": badge,
        "isLocked": is_locked,
        "isWindows": is_windows,
        "isEsp": is_esp,
        "isLive": is_live_disk,
        "isTooSmall": is_too_small,
        "selectable": selectable,
        "recommended": False,
        "requiresConfirm": True,
        "espFreeMib": esp_free_mib,
        "espLowSpace": esp_low_space,
        "espPath": "",
        "espKname": "",
        "mounts": mounts,
    }


def scan_storage(allow_privileged: bool = True) -> dict:
    """Scan local block devices and return protected/selectable storage topology."""
    if not shutil.which("lsblk"):
        return {"disks": [], "esps": [], "recommendedTargetId": "", "preview": False, "error": "lsblk unavailable"}

    res = subprocess.run(
        [
            "lsblk", "-J", "-b", "-p", "-o",
            "NAME,KNAME,PATH,SIZE,FSTYPE,LABEL,PARTLABEL,PARTTYPE,UUID,MOUNTPOINTS,RM,RO,TRAN,TYPE,MODEL,PTTYPE,PKNAME",
        ],
        capture_output=True, text=True, timeout=10, check=False,
    )
    if res.returncode != 0:
        return {"disks": [], "esps": [], "recommendedTargetId": "", "preview": False, "error": res.stderr.strip()}

    raw = json.loads(res.stdout or "{}")
    live_disks = detect_live_disk_paths()

    disks = []
    all_esps = []

    for dev in raw.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue
        kname = dev.get("kname") or ""
        path = dev.get("path") or f"/dev/{kname}"
        size_b = int(dev.get("size") or 0)
        if kname.startswith(("zram", "loop", "sr", "ram", "fd")) or size_b <= 0:
            continue

        is_live_disk = (path in live_disks) or any(
            (c.get("path") in live_disks) for c in (dev.get("children") or [])
        )
        pttype = (dev.get("pttype") or "").lower()
        model = (dev.get("model") or "Local Disk").strip()
        tran = (dev.get("tran") or "internal").lower()

        segments = []
        disk_esps = []
        for child in dev.get("children") or []:
            if child.get("type") != "part":
                continue
            seg = _classify_partition(child, path, kname, is_live_disk, allow_mount=allow_privileged)
            segments.append(seg)
            if seg["isEsp"] and not is_live_disk:
                disk_esps.append(seg)
                all_esps.append(seg)

        if not is_live_disk:
            for idx, gap in enumerate(probe_unallocated_regions(path)):
                g_size = gap["sizeBytes"]
                can_pick = g_size >= MIN_TARGET_BYTES
                segments.append({
                    "id": f"unalloc:{path}:{gap['startBytes']}",
                    "kind": "unallocated",
                    "diskPath": path,
                    "diskKname": kname,
                    "partPath": "",
                    "partKname": "",
                    "displayName": f"Unallocated Free Space #{idx + 1} on {path}",
                    "sizeBytes": g_size,
                    "sizeLabel": _human_size(g_size),
                    "fstype": "free",
                    "label": "Unallocated Space",
                    "badgeText": "Recommended (Clean Dual-Boot)" if can_pick else "Free Space (< 20 GB)",
                    "isLocked": False,
                    "isWindows": False,
                    "isEsp": False,
                    "isLive": False,
                    "isTooSmall": not can_pick,
                    "selectable": can_pick,
                    "recommended": can_pick,
                    "requiresConfirm": False,
                    "espFreeMib": None,
                    "espLowSpace": False,
                    "espPath": "",
                    "espKname": "",
                    "mounts": [],
                })

        disks.append({
            "path": path,
            "kname": kname,
            "model": model,
            "sizeBytes": size_b,
            "sizeLabel": _human_size(size_b),
            "pttype": pttype or "none",
            "tran": tran,
            "isLiveMedia": is_live_disk,
            "lockedReason": "Live USB Boot Medium (Locked)" if is_live_disk else "",
            "segments": segments,
            "hasEsp": len(disk_esps) > 0,
        })

    # Attach preserved ESP metadata to every selectable target
    recommended_id = ""
    fallback_id = ""
    global_esp = all_esps[0] if all_esps else None
    for d in disks:
        disk_esp = next((s for s in d["segments"] if s["isEsp"]), None) or global_esp
        for seg in d["segments"]:
            if not seg["selectable"]:
                continue
            if disk_esp:
                seg["espPath"] = disk_esp["partPath"]
                seg["espKname"] = disk_esp["partKname"]
                seg["espFreeMib"] = disk_esp["espFreeMib"]
                seg["espLowSpace"] = disk_esp["espLowSpace"]
            elif seg["kind"] == "partition":
                # Single pre-existing partition mode requires an existing ESP on the system
                seg["selectable"] = False
                seg["badgeText"] = "No EFI Partition Found on System"
            if seg["recommended"] and not recommended_id:
                recommended_id = seg["id"]
            elif seg["selectable"] and not fallback_id:
                fallback_id = seg["id"]

    return {
        "disks": disks,
        "esps": all_esps,
        "recommendedTargetId": recommended_id or fallback_id,
        "preview": False,
        "error": "",
    }


def validate_target_selection(target_id: str) -> tuple:
    """Independently re-probe hardware and validate a requested install target ID."""
    if not target_id:
        raise ValueError("No target partition or free space was selected.")

    topo = scan_storage(allow_privileged=True)
    for disk in topo.get("disks", []):
        for seg in disk.get("segments", []):
            if seg["id"] != target_id:
                continue
            if disk.get("isLiveMedia") or seg.get("isLive"):
                raise ValueError(f"Refused: {target_id} belongs to the active Live USB boot disk.")
            if seg.get("isWindows"):
                raise ValueError(f"Refused: {target_id} is protected Windows/NTFS/BitLocker storage.")
            if seg.get("isEsp"):
                raise ValueError(f"Refused: {target_id} is a protected EFI System Partition.")
            if seg.get("sizeBytes", 0) < MIN_TARGET_BYTES:
                raise ValueError(f"Refused: {target_id} is smaller than 20 GiB minimum.")
            if not seg.get("selectable"):
                raise ValueError(f"Refused: {target_id} is locked or ineligible ({seg.get('badgeText')}).")
            return seg, disk, topo

    raise ValueError(f"Selected install target no longer exists or is locked: {target_id}")


def preview_sample_storage() -> dict:
    """Deterministic sample layout for UI testing under --preview only."""
    return {
        "preview": True,
        "error": "",
        "recommendedTargetId": "unalloc:/dev/nvme0n1:204800000000",
        "esps": [
            {"partPath": "/dev/nvme0n1p1", "partKname": "nvme0n1p1", "espFreeMib": 28, "espLowSpace": True}
        ],
        "disks": [
            {
                "path": "/dev/nvme0n1",
                "kname": "nvme0n1",
                "model": "NVMe SSD (Dual-Boot Preview)",
                "sizeBytes": 512110190592,
                "sizeLabel": "476.9 GB",
                "pttype": "gpt",
                "tran": "nvme",
                "isLiveMedia": False,
                "lockedReason": "",
                "hasEsp": True,
                "segments": [
                    {
                        "id": "part:/dev/nvme0n1p1",
                        "kind": "partition",
                        "diskPath": "/dev/nvme0n1",
                        "diskKname": "nvme0n1",
                        "partPath": "/dev/nvme0n1p1",
                        "partKname": "nvme0n1p1",
                        "displayName": "EFI System (/dev/nvme0n1p1)",
                        "sizeBytes": 104857600,
                        "sizeLabel": "100 MB",
                        "fstype": "vfat",
                        "label": "SYSTEM",
                        "badgeText": "EFI System Partition (Preserved)",
                        "isLocked": True,
                        "isWindows": False,
                        "isEsp": True,
                        "isLive": False,
                        "isTooSmall": False,
                        "selectable": False,
                        "recommended": False,
                        "requiresConfirm": False,
                        "espFreeMib": 28,
                        "espLowSpace": True,
                        "espPath": "/dev/nvme0n1p1",
                        "espKname": "nvme0n1p1",
                    },
                    {
                        "id": "part:/dev/nvme0n1p3",
                        "kind": "partition",
                        "diskPath": "/dev/nvme0n1",
                        "diskKname": "nvme0n1",
                        "partPath": "/dev/nvme0n1p3",
                        "partKname": "nvme0n1p3",
                        "displayName": "Windows 11 (/dev/nvme0n1p3)",
                        "sizeBytes": 300647710720,
                        "sizeLabel": "280.0 GB",
                        "fstype": "ntfs",
                        "label": "Windows",
                        "badgeText": "Windows Protected",
                        "isLocked": True,
                        "isWindows": True,
                        "isEsp": False,
                        "isLive": False,
                        "isTooSmall": False,
                        "selectable": False,
                        "recommended": False,
                        "requiresConfirm": False,
                        "espFreeMib": None,
                        "espLowSpace": False,
                        "espPath": "",
                        "espKname": "",
                    },
                    {
                        "id": "unalloc:/dev/nvme0n1:204800000000",
                        "kind": "unallocated",
                        "diskPath": "/dev/nvme0n1",
                        "diskKname": "nvme0n1",
                        "partPath": "",
                        "partKname": "",
                        "displayName": "Unallocated Free Space #1 on /dev/nvme0n1",
                        "sizeBytes": 107374182400,
                        "sizeLabel": "100.0 GB",
                        "fstype": "free",
                        "label": "Unallocated Space",
                        "badgeText": "Recommended (Clean Dual-Boot)",
                        "isLocked": False,
                        "isWindows": False,
                        "isEsp": False,
                        "isLive": False,
                        "isTooSmall": False,
                        "selectable": True,
                        "recommended": True,
                        "requiresConfirm": False,
                        "espFreeMib": 28,
                        "espLowSpace": True,
                        "espPath": "/dev/nvme0n1p1",
                        "espKname": "nvme0n1p1",
                    },
                    {
                        "id": "part:/dev/nvme0n1p5",
                        "kind": "partition",
                        "diskPath": "/dev/nvme0n1",
                        "diskKname": "nvme0n1",
                        "partPath": "/dev/nvme0n1p5",
                        "partKname": "nvme0n1p5",
                        "displayName": "Linux Data (/dev/nvme0n1p5)",
                        "sizeBytes": 75161927680,
                        "sizeLabel": "70.0 GB",
                        "fstype": "ext4",
                        "label": "Linux Data",
                        "badgeText": "Existing Non-Windows Partition",
                        "isLocked": False,
                        "isWindows": False,
                        "isEsp": False,
                        "isLive": False,
                        "isTooSmall": False,
                        "selectable": True,
                        "recommended": False,
                        "requiresConfirm": True,
                        "espFreeMib": 28,
                        "espLowSpace": True,
                        "espPath": "/dev/nvme0n1p1",
                        "espKname": "nvme0n1p1",
                    },
                ],
            },
            {
                "path": "/dev/sda",
                "kname": "sda",
                "model": "SanDisk Live USB",
                "sizeBytes": 31000000000,
                "sizeLabel": "28.9 GB",
                "pttype": "gpt",
                "tran": "usb",
                "isLiveMedia": True,
                "lockedReason": "Live USB Boot Medium (Locked)",
                "hasEsp": False,
                "segments": [],
            },
        ],
    }


if __name__ == "__main__":
    print(json.dumps(scan_storage(allow_privileged=(os.geteuid() == 0)), indent=2))
