---
trigger: model_decision
description: "Apply when configuring KDE Plasma 6 Wayland layouts, Fcitx5 Indic typing, 4 GB RAM ZRAM/Baloo tuning, Realtek Wi-Fi, firewalld, systemd-resolved, Waydroid, DSC tokens, or offline Indic AI helpers."
---

# India-First Hardware, Low-RAM & KDE Plasma 6 Wayland Specifications

### 4 GB RAM Survival Stack:
- `/etc/systemd/zram-generator.conf`: `[zram0]`, `zram-size = ram`, `compression-algorithm = zstd`, `swap-priority = 100`.
- `/etc/sysctl.d/99-zram.conf`: `vm.swappiness = 133`.
- Install & enable `earlyoom.service`.
- Provide `ujust low-ram-mode` toggle using `kwriteconfig6` to disable Baloo (`baloofilerc`, group `Basic Settings`, key `Indexing-Enabled = false`), reduce `AnimationDurationFactor`, and disable KWin blur (`kwinrc`, group `Plugins`, key `blurEnabled = false`).

### Realtek Wi-Fi Mitigation (RTL8852BE / rtw89):
- Create `/etc/modprobe.d/rtw89.conf` with:
  ```ini
  options rtw89_pci disable_clkreq=y disable_aspm_l1=y disable_aspm_l1ss=y
  options rtw89_core disable_ps_mode=y
  ```
- Create `/etc/NetworkManager/conf.d/wifi-powersave-off.conf` with:
  ```ini
  [connection]
  wifi.powersave = 2
  ```
- Ensure `realtek-firmware` is installed and `type: initramfs` runs afterward.

### Indic Typing (Fcitx5 + m17n on KDE Wayland):
- Install `fcitx5`, `fcitx5-m17n`, `m17n-db`, `kcm-fcitx5`, `fcitx5-configtool`, `lohit-devanagari-fonts`.
- Set **ONLY** `XMODIFIERS=@im=fcitx` in `/etc/environment`. Do **NOT** set `GTK_IM_MODULE` or `QT_IM_MODULE` globally.
- Configure `/etc/skel/.config/kwinrc` under `[Wayland]` with:
  ```ini
  InputMethod[$e]=/usr/share/applications/fcitx5-wayland-launcher.desktop
  VirtualKeyboardEnabled=true
  ```
- Disable `/etc/xdg/autostart/org.fcitx.Fcitx5.desktop` to prevent KWin duplicate-launch warnings. Do **NOT** add KIMPanel to Plasma panels.

### KDE Plasma 6 Layout Switcher (`qdbus6`):
- Invoke via: `qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "$(cat <script.js>)"` (with `/usr/lib/qt6/bin/qdbus` fallback).
- Use Plasma 6 API string properties: `panel.location`, `panel.lengthMode` (`"fill"`, `"fit"`, `"custom"`), `panel.alignment`, `panel.hiding` (`"none"`, `"autohide"`, `"dodgewindows"`), `panel.floating`.
- Clearly document that Global Menu (`org.kde.plasma.appmenu`) works on Qt/KDE/Chrome apps, but NOT reliably on GTK3/4, native Wayland Electron apps, or Firefox without caveats.

### Networking, Security & Peripherals:
- `/etc/systemd/resolved.conf.d/10-dot-opportunistic.conf`: `FallbackDNS=9.9.9.9#dns.quad9.net 1.1.1.1#one.one.one.one` and `DNSOverTLS=opportunistic` (never strict `yes`).
- `firewalld`: declarative zone XML under `/etc/firewalld/zones/kushagra-workstation.xml` avoiding blanket 1025-65535 open ports while explicitly permitting `kdeconnect` (1714-1764 TCP/UDP), `mdns`, `ipp-client`, and `dhcpv6-client`. Update `DefaultZone=kushagra-workstation` via `sed` in build script.
- Bake `opensc` + `pcsc-lite-ccid` + enable `pcscd.socket` for Feitian ePass2003 DSC tokens. Document Watchdata ProxKey (`pcscd_wd` clash) and Mantra/Morpho L1 RD Windows-first caveats honestly.
- `ujust setup-waydroid`: configure firewalld trusted zone (`waydroid0`, 67/udp, 53/udp, `--add-forward`), detect NVIDIA GPUs to apply `ro.hardware.egl=swiftshader` + `ro.hardware.gralloc=default` in `/var/lib/waydroid/waydroid.cfg`, and remind users about LiveCD and Play Integrity/UPI limits.
