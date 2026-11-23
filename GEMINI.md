Project Constitution: Kushagra OS (Fedora Atomic Kinoite 44 + BlueBuild)

Core Mission
Build a reliable, unbreakable, immutable desktop Linux operating system tailored for universal desktop use and Indian hardware (including 4 GB RAM laptops), powered by Universal Blue (ghcr.io/ublue-os/kinoite-main:44), KDE Plasma 6 (Wayland), and modern BlueBuild CI/CD.

Non-Negotiable Engineering Invariants

Modern BlueBuild Only (2026 Schema):
- ALWAYS use `type: dnf` (dnf5) — NEVER use deprecated `type: rpm-ostree` or deprecated `optfix:`.
- ALWAYS use `default-flatpaks` v2 (`configurations:` array with `scope:`) — NEVER use v1 `user:`/`system:` top-level keys or `remove:`.
- ALWAYS place system config overlays in `files/system/etc/` (mapped to `/etc/`) — NEVER write to `/usr/etc/` and NEVER copy files into symlinked targets (`/home`, `/opt`, `/srv`, `/root`, `/usr/local`, `/mnt`, `/tmp`).
- ALWAYS place custom ujust recipes strictly in `files/system/usr/share/ublue-os/just/60-custom.just` (other filenames are silently ignored by Universal Blue).
- ALWAYS include `type: initramfs` ONCE near the end of `recipes/recipe.yml` whenever modifying `/etc/modprobe.d/`, `/etc/modules-load.d/`, `dracut.conf.d/`, or Plymouth.
- NEVER leave empty YAML keys (use `[]`, `{}`, or omit the key).
- NEVER run `dnf5 remove` on shared utility packages like `jq` during scripts (risks cascading package deletion).
- NEVER strip `VERSION_ID` from `/etc/os-release` when using `type: os-release`.
- Custom local modules MUST declare `source: local` and use `jq` + `get_json_array` (NOT `yq`).

Honest Compatibility & Security Guardrails:
- NEVER promise or hack around Google Play Integrity for Indian UPI/banking apps (GPay, PhonePe, DigiLocker) inside Waydroid.
- NEVER set global `GTK_IM_MODULE=fcitx` or `QT_IM_MODULE=fcitx` in `/etc/environment` on KDE Plasma 6 Wayland (use KWin Virtual Keyboard + `XMODIFIERS=@im=fcitx` only).
- NEVER enable strict `DNSOverTLS=yes` globally in systemd-resolved (breaks Indian hotel/rail/airport captive portals; use `FallbackDNS=` + `DNSOverTLS=opportunistic`).
- NEVER ship `sarvam-1` base weights as a conversational chatbot (it is a text-completion base model).
- NEVER commit `cosign.key` or any private credentials to Git. Only `cosign.pub` belongs in the repository root.

Execution Discipline:
- Always inspect existing files before editing. Do not guess filenames or upstream schemas.
- Every shell script in `files/scripts/` MUST end in `.sh` and begin with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Before declaring any task complete, validate YAML syntax, run `bash -n` (and shellcheck if installed), and verify bluebuild generate output if CLI is available.
- Never delete or silently overwrite this `GEMINI.md` file.
