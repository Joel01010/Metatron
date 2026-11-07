# Metatron Spectral Theme Studio

The v1.4 UI upgrade keeps customization inside the existing `appearance` and `presence` settings namespaces. No cosmetic feature adds a Tauri command or a second settings database.

## Presets

- **Spectral Rose** — Metatron default: near-black rose materials with a warm intelligence core.
- **Obsidian** — graphite and monochrome intelligence glow.
- **Aurora** — midnight navy, cyan and indigo.
- **Ember** — charcoal, copper and amber.
- **Porcelain** — first-class warm light theme with graphite text and restrained gold.
- **Custom** — entered automatically when preset-defining colors/materials are changed or a theme JSON file is imported.

## Safe theme JSON

Theme files use schema `1` and may contain only `schema`, `id`, `name`, `appearance` and `presence` at the top level. Appearance and Presence keys are separately allowlisted in `ui/app.js`. Unknown keys are rejected. No raw CSS, HTML, JavaScript, URLs or asset paths are accepted.

Numeric values are clamped by the UI importer and then validated by `metatron/settings.py`. Hex colors must use `#RRGGBB`. Backend validation remains authoritative.

## Performance rules

Theme switching changes CSS variables and renderer uniforms; it does not rebuild the workspace tree or start another WebGL renderer. The Presence stage uses static CSS gradients/grid material plus the existing canonical `ui/orb-renderer.js`. Reduced motion lowers orb motion/FPS and suppresses CSS animation/transition duration.

## Release status

Portable tests and product/security audit can validate structure and contracts on Linux. Windows `cargo fmt --check`, `cargo check`, desktop build, idle-memory benchmark, orb probe and soak remain required after visual changes before declaring the UI release-ready.
