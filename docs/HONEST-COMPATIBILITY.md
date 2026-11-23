# Kushagra OS — Honest Hardware & Compatibility Guide

This document establishes the real-world operational boundaries, verified hardware support, and known upstream limitations for **Kushagra OS (v0.1 Prototype)**.

---

## 1. Local Testing Runbook (Windows Host)

### A. VMware Workstation Pro (Recommended VM)
- **Status:** 100% Free for personal and commercial use since November 2024.
- **Recommended Versions:** `25H2` or `17.6.x` (November 2026 releases like `26H1u1 / 26.0.1` have observed Wayland copy-paste issues).
- **VM Configuration:**
  - Guest OS: Linux -> Fedora 64-bit.
  - Firmware: UEFI (with Secure Boot enabled).
  - Acceleration: Enable **Accelerate 3D Graphics** with at least 1 GB graphics memory.
  - Memory: Allocate at least 3 GB RAM (4 GB recommended).

### B. VirtualBox 7.2 (Alternative)
- **Graphics Controller:** Must be set to **VMSVGA** with **Enable 3D Acceleration** checked.
  > ⚠️ **CRITICAL:** Running KDE Plasma 6 Wayland without 3D Acceleration in VirtualBox results in a persistent black screen (KDE Bug #481937).
- Note for AMD GPU Windows hosts: Minor Wayland mouse pointer latency has been reported on VirtualBox 7.2.

### C. QEMU on Windows (-accel whpx)
- Use Windows Hypervisor Platform acceleration:
  ```powershell
  qemu-system-x86_64.exe -accel whpx -M q35 -m 4096 -smp 4 `
    -drive if=pflash,format=raw,readonly=on,file=OVMF_CODE.fd `
    -drive if=pflash,format=raw,file=OVMF_VARS.fd `
    -cdrom KushagraOS-44.iso -boot d -vga virtio
  ```

---

## 2. Bare-Metal USB Flashing

When flashing `KushagraOS-44.iso` to a physical USB thumb drive:
- **Fedora Media Writer (Top Pick):** Cross-platform, validates sector writes automatically.
- **Rufus:** Must be flashed in **DD Image Mode**.
  > ⚠️ **CRITICAL:** Do NOT choose *ISO Image Mode* in Rufus. ISO mode replaces the syslinux/GRUB boot chain and breaks atomic boot validation.
- **Ventoy:** Supported out of the box (handles >4 GB ISO files seamlessly).

---

## 3. Atomic Updates & Recovery Runbook

Kushagra OS uses **bootc** (bootable container) architecture. System updates are downloaded and staged atomically in the background:
```bash
# Check status of current and staged deployment
sudo bootc status

# Upgrade to latest image
sudo bootc upgrade

# Emergency Rollback after an update or power-cut during boot
sudo bootc rollback
```
Alternatively, select the previous deployment in the GRUB boot menu to roll back byte-for-byte.

---

## 4. Hardware Compatibility & Real Boundaries

### A. Android Apps (Waydroid) vs. Indian UPI & Banking
- **Hardware Acceleration:** Native on Intel (Iris Xe / UHD) and AMD (Radeon) GPUs.
- **NVIDIA Fallback:** Configured automatically via `ujust setup-waydroid` to use SwiftShader software rendering.
- **Google Play Integrity Hard Limit:**
  > ⚠️ **CRITICAL:** Waydroid **CANNOT** pass hardware-backed `MEETS_STRONG_INTEGRITY` or `MEETS_DEVICE_INTEGRITY`.
  > Apps including **Google Pay (GPay)**, **PhonePe**, **Paytm**, **DigiLocker**, and major Indian banking apps will refuse to run or fail at SMS device verification. Kushagra OS does not ship fragile Magisk/Zygisk spoofing modules.

### B. Indian DSC (Digital Signature) Tokens
- **Feitian ePass2003:** Fully supported out of the box via standard USB CCID driver (`pcsc-lite-ccid`, `opensc`, `pcscd.socket`).
- **Watchdata ProxKey:** Incompatible with standard OpenSC. ProxKey requires vendor-proprietary `pcscd_wd` daemon which conflicts with the system PC/SC daemon.
- **Mantra MFS110 & Morpho MSO 1300 E3 (L1 Biometrics):** UIDAI L1 RD services ship Windows and Android installers; no verified public L1 RD service exists for immutable Fedora Atomic systems.

### C. Printers & Scanners
- **Modern IPP Everywhere / AirScan:** Fully supported driverless via `cups.socket`, `avahi-daemon.socket`, and `ipp-usb`.
- **Legacy HP All-in-Ones (e.g., M1217nfw, M127FW):** Require proprietary `hp-plugin` which cannot be retained across reboots on an immutable root filesystem without container overlays.

### D. Media & Creative Software
- **DaVinci Resolve (Free on Linux):** Does not support hardware decoding/encoding of H.264/H.265 or AAC audio without paid Studio license or intermediate transcode to DNxHR/ProRes via FFmpeg. Use pre-installed **Kdenlive** for native H.264/AAC editing.

### E. Gaming & Kernel-Level Anti-Cheat
- Games requiring Windows kernel-level anti-cheat (e.g., **Valorant Vanguard**, **Fortnite EAC Linux v2**) will **NOT** run on Linux. Use a dual-boot setup for these titles. Standard Windows executables run securely via pre-installed **Bottles** and Proton runners.
