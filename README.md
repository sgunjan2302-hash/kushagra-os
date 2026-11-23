# Kushagra OS (v0.1 Prototype)

> **An unbreakable, India-first universal desktop operating system combining familiar desktop UX, low-RAM resilience, and immutable cloud-native reliability.**

[![Build Kushagra OS](https://github.com/kushagra-os/kushagra-os/actions/workflows/build.yml/badge.svg)](https://github.com/kushagra-os/kushagra-os/actions/workflows/build.yml)
[![LiveCD ISO](https://github.com/kushagra-os/kushagra-os/actions/workflows/iso.yml/badge.svg)](https://github.com/kushagra-os/kushagra-os/actions/workflows/iso.yml)

---

## Highlights

- **Base System:** Built on **Universal Blue (Fedora Atomic Kinoite 44)** with KDE Plasma 6 (Wayland) and bootc image-as-OS architecture.
- **Adaptive UI:** Switch effortlessly between **Familiar Mode** (Windows-like bottom panel) and **Studio Mode** (macOS-like top bar + centered floating dock) via `kushagra-layout-switch`.
- **4 GB Low-RAM Tuning:** Pre-tuned ZRAM (`zstd` algorithm, 100% RAM allocation, `vm.swappiness = 133`) and `earlyoom` memory watchdog daemon.
- **India-First Hardware & IME:** Native Fcitx5 + m17n phonetic typing (zero candidate-window flickering under Wayland), Feitian ePass2003 DSC token support, and Realtek RTL8852BE Wi-Fi power-save dropouts mitigation.
- **App Ecosystem:** Pre-configured Flathub Flatpaks (Firefox, Bottles, OnlyOffice, Kdenlive, Flatseal, Mission Center) and automated Waydroid subsystem integration.
- **Atomic Reliability:** Power-cut immune updates via `sudo bootc upgrade` and single-command rollback via `sudo bootc rollback`.

---

## Quickstart & ujust Commands

Kushagra OS provides custom management recipes via `ujust`:

```bash
# Switch desktop layout (Familiar vs. Studio)
ujust switch-layout [classic|floating]

# Toggle 4 GB low-RAM performance mode (disables Baloo indexing & KWin blur)
ujust low-ram-mode [enable|disable|status]

# Configure Waydroid Android subsystem network routing
ujust setup-waydroid

# View hardware-tiered Indic speech & LLM guide
ujust setup-indic-ai

# Diagnose connected USB DSC smart card tokens
ujust check-dsc-token

# Run full system health verification check
ujust health-check
```

---

## Verifying Image Signatures (Cosign)

All published container images are cryptographically signed:

```bash
cosign verify \
  --key cosign.pub \
  ghcr.io/<your-github-username>/kushagra-os:44
```

---

## Documentation Links

- [Honest Hardware & Compatibility Guide](docs/HONEST-COMPATIBILITY.md) — Windows VM testing runbook, USB flashing instructions, and hardware boundaries.
- [Project Constitution](GEMINI.md) — Non-negotiable architectural invariants and 2026 BlueBuild schema rules.
