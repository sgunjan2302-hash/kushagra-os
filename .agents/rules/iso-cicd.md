---
trigger: glob
globs: ".github/workflows/*.yml, **/iso.yaml"
description: "GitHub Actions CI/CD, BlueBuild action v1.14, Titanoboa LiveCD iso.yaml contract, and Cloudflare R2 ISO upload rules."
---

# CI/CD & ISO Pipeline Rules (2026)

### Image Build Workflow (`.github/workflows/build.yml`):
- Use `blue-build/github-action@v1.14.0` (or `@v1`).
- Pass required inputs: `recipe: recipes/recipe.yml`, `cosign_private_key: ${{ secrets.SIGNING_SECRET }}`, `pr_event_number: ${{ github.event.number }}`.
- Keep `maximize_build_space: 'true'`.
- Start with `chunkah: 'false'` for fast iteration; document enabling `chunkah: 'true'` for production releases. **NEVER** use legacy `rechunk: 'true'`.

### LiveCD ISO Workflow (`.github/workflows/iso.yml`):
- Primary LiveCD builder: `ublue-os/titanoboa@main` (requires `/usr/lib/bootc-image-builder/iso.yaml` baked inside the container image with `label: "KushagraOS-44"`, `grub2.default`, `grub2.timeout`, and `grub2.entries`).
- Fallback non-live installer builder: `JasonN3/build-container-installer@v1.5.0` (`iso_name`, `iso_path`).
- Always generate a `sha256sum` checksum file alongside the `.iso`.
- **NEVER** attempt to upload a single >2 GiB ISO file directly to GitHub Releases. Upload full ISOs to S3-compatible Cloudflare R2 via secrets (`R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`), or split into <2 GiB parts with checksums if using GitHub Releases fallback.
