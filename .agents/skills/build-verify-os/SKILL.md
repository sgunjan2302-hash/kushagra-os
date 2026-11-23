---
name: build-verify-os
description: Run pre-commit validation, YAML schema checks, shell syntax checks, and local BlueBuild Containerfile generation checks before pushing OS changes.
---

# Build & Verification Checklist

Execute these verification steps sequentially before declaring any OS build milestone complete:

### 1. Secret Safety Audit:
- Confirm `cosign.key` or `.private` files are NOT staged or tracked by Git (`git status`, `.gitignore` check).
- Confirm `.gitignore` ignores `*.key`, `*.private`, `*.secret`.

### 2. YAML & BlueBuild Anti-Pattern Scan:
- Parse every `.yml` / `.yaml` file under `recipes/` and `.github/workflows/` with Python `yaml.safe_load` to guarantee zero syntax errors.
- Verify **ZERO** occurrences of `type: rpm-ostree`, `optfix:`, `/usr/etc/`, or `default-flatpaks` v1 keys (`user:`, `system:`, `remove:` at top level).
- Verify `type: initramfs` appears exactly **ONCE** and near the end of `recipes/recipe.yml`.
- Verify `files/system/usr/share/ublue-os/just/60-custom.just` is used for all custom ujust recipes.

### 3. Shell, Firewall XML & Plasma JS Validation:
- Verify every script in `files/scripts/` has `#!/usr/bin/env bash`, `set -euo pipefail`, and passes `bash -n` (and `shellcheck` if installed).
- Parse any custom `/etc/firewalld/zones/*.xml` files with Python `xml.etree.ElementTree` to verify valid XML.
- Verify `/etc/environment` contains **ONLY** `XMODIFIERS=@im=fcitx` for IME (no global `GTK_IM_MODULE` or `QT_IM_MODULE`).
- Verify `files/system/usr/lib/bootc-image-builder/iso.yaml` exists and defines `label: "KushagraOS-44"` and `grub2.entries` for Titanoboa.

### 4. Dry-Run Generation (if bluebuild CLI is installed):
- Run `bluebuild generate -d ./recipes/recipe.yml` to verify full recipe expansion and strict schema validation.
- Report exact command outputs, pass/fail status, and manual steps needed (such as setting `SIGNING_SECRET` in GitHub Actions).
