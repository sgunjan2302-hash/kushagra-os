---
trigger: glob
globs: "recipes/**/*.yml, recipes/**/*.yaml"
description: "Strict 2026 BlueBuild recipe.yml, dnf, default-flatpaks v2, systemd, os-release, and initramfs YAML validation rules."
---

# BlueBuild YAML Schema Guardrails (2026)

When creating or modifying any file under `recipes/`:

### Top-Level recipe.yml Fields:
- **Required:** `name` (`kushagra-os`), `description`, `base-image` (`ghcr.io/ublue-os/kinoite-main`), `image-version` (`44`), `modules`.
- Split large package and flatpak sections into `recipes/*.yml` and include via `- from-file: <filename>.yml`.

### `type: dnf` Exact Syntax:
- Use `repos:` (`files:`, `copr:`, `keys:`, `nonfree: true`).
- Use `install:` with `skip-unavailable: true` and `packages:`.
- **NEVER** include `optfix:` (deprecated since BlueBuild CLI v0.9.23).
- **NEVER** install `fcitx5-autostart` (injects conflicting `/etc/profile.d` env vars on KDE Wayland).
- Keep removals minimal (`remove:` -> `packages:`).

### `type: default-flatpaks` (v2) Exact Syntax:
- Must wrap entries under `configurations:` list.
- Valid keys per entry: `notify` (bool), `scope` (`system` | `user`), `repo-url`, `repo-name`, `install` (list of verified Flathub App IDs).
- **NEVER** use legacy v1 top-level `user:`/`system:` keys or `remove:`.
- Verified Flathub IDs: `org.mozilla.firefox`, `org.onlyoffice.desktopeditors`, `org.kde.kdenlive`, `com.usebottles.bottles`, `com.github.tchx84.Flatseal`, `io.github.flattool.Warehouse`, `io.missioncenter.MissionCenter`.

### Module Ordering:
- Place in sequence: `files` -> `dnf` -> `script` -> `systemd` -> `default-flatpaks` -> `os-release` -> `signing` -> `initramfs` (run once near end).
