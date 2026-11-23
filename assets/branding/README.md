# Kushagra OS — Branding & Visual Asset Specifications

This directory contains specifications and vector master assets for Kushagra OS (v0.1 Prototype). Follow these exact specifications when adding or updating visual assets.

---

## 1. Logo Assets

### `logo-symbol.svg` (Primary Icon / Mark)
- **Format:** Scalable Vector Graphics (`.svg`), SVG 1.1 or 2.0 compliant.
- **ViewBox:** `0 0 512 512` (Square, 1:1 aspect ratio).
- **Safe Zone:** Keep core graphic within inner 448x448 bounds (32px padding).
- **Color Palette:**
  - Saffron (Energy / Innovation): `#FF9933` / `rgb(255, 153, 51)`
  - Chakra Navy (Trust / Stability): `#002244` / `rgb(0, 34, 68)`
  - Clean White: `#FFFFFF` / `rgb(255, 255, 255)`
  - India Green (Growth): `#128807` / `rgb(18, 136, 7)`
- **Target Installation:** `/usr/share/pixmaps/kushagra-logo.svg` and scaled to `/usr/share/icons/hicolor/<size>/apps/kushagra-logo.png`.

### `logo-full.svg` (Horizontal Logotype)
- **Format:** Scalable Vector Graphics (`.svg`).
- **ViewBox:** `0 0 1200 300` (Horizontal 4:1 aspect ratio).
- **Elements:** Symbol mark on the left + "KUSHAGRA" in bold modern geometric sans-serif + "OS" badge in subtle accent.
- **Usage:** KDE Kickoff menu banner, installer welcome screen, fastfetch banner.

---

## 2. Icon Export Resolutions
When generating PNG exports from `logo-symbol.svg`, render the following standard icon sizes:
```
/usr/share/icons/hicolor/
├── 16x16/apps/kushagra-logo.png
├── 24x24/apps/kushagra-logo.png
├── 32x32/apps/kushagra-logo.png
├── 48x48/apps/kushagra-logo.png
├── 64x64/apps/kushagra-logo.png
├── 128x128/apps/kushagra-logo.png
├── 256x256/apps/kushagra-logo.png
└── 512x512/apps/kushagra-logo.png
```

---

## 3. Plymouth Boot Splash Theme
Located in `assets/plymouth/`:
- **Theme Name:** `kushagra`
- **File:** `assets/plymouth/kushagra-logo.png`
- **Resolution:** 256x256 or 512x512 with transparent background.
- **Configuration:** `kushagra.plymouth` (Two-step or BGRT-compatible spinner theme).

---

## 4. Wallpapers
Located in `assets/wallpapers/`:
- **Default Light:** `kushagra-default-light.png`
  - Dimensions: `3840 x 2160` (4K UHD)
  - Color Profile: sRGB
- **Default Dark:** `kushagra-default-dark.png`
  - Dimensions: `3840 x 2160` (4K UHD)
  - Color Profile: sRGB
- **Target Installation:** `/usr/share/wallpapers/Kushagra/`
