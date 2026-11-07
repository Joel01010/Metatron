# Metatron v1.4 Spectral UI Upgrade — Validation Report

Date: 2026-11-06
Status: **portable candidate validated; Windows requalification still required**

## Implemented

### Phase 0 — qualified-baseline canonicalization
- Replaced the v1.4 qualification wrapper's positional array splat with PowerShell hashtable splatting.
- Reworked `Test-OrbWindow.ps1` so it launches and cleans up the desktop executable itself.
- Corrected native `FindWindow` class-name marshaling to `[NullString]::Value`.
- Added regression assertions covering both Windows fixes.
- The baseline Rust source is already documented as rustfmt-normalized. Rust tooling is not installed in this Linux sandbox, so `cargo fmt --check` was not rerun here and remains a Windows/native release gate.

### Phase 1 — semantic design system
- Rebuilt `ui/styles.css` around semantic background/surface/text/border/status/shadow/radius/motion tokens.
- Added token-driven density, motion, sidebar and material behavior.
- Preserved system fonts and avoided bundled font/assets cost.

### Phase 2 — Presence Stage
- Replaced the flat Home Presence area with a deep procedural stage.
- Kept `ui/orb-renderer.js` as the single canonical WebGL renderer.
- Limited stage telemetry to verified route, managed memory and privacy state.
- Added a dark fallback stage behind the iframe so renderer/transparency failure cannot become a large white void.
- Added dashboard iframe `postMessage` ingestion and settings synchronization for both dashboard and floating Presence.
- Added live orb opacity plus reduced-motion/motion-profile behavior.

### Phase 3 — Home/navigation polish
- Reworked header hierarchy and local-control-plane status treatment.
- Consolidated the health rail to four high-value system summaries.
- Added active sidebar rail/light behavior and compact sidebar mode.
- Differentiated dictation, memory-governor, quick-action, workflow, activity and agent card families.
- Added improved focus states, empty states and loading skeletons.

### Phase 4 — Theme Studio
Five presets plus Custom are implemented:
- Spectral Rose
- Obsidian
- Aurora
- Ember
- Porcelain

Theme Studio controls:
- accent
- intelligence/core color
- background
- surface tint
- material strength
- border strength
- glow strength
- corner family
- density
- font scale
- motion profile
- sidebar mode
- reduced motion
- Presence quality, scale, opacity, plasma, particles, bloom and interaction gain

Theme JSON import/export:
- schema 1
- strict top-level and section key allowlists
- unknown keys rejected
- colors constrained to `#RRGGBB`
- numeric values clamped in the importer and validated again by the backend
- no raw CSS/HTML/JavaScript injection path

### Phase 5 — interaction/accessibility
- Visible keyboard focus styling.
- Command palette arrow-key and Enter navigation.
- `prefers-reduced-motion` and persisted reduced-motion handling.
- Motion profiles also reduce canonical orb FPS/time progression instead of adding another renderer.
- Light Porcelain is explicitly styled rather than inverted.

## Security / architecture invariants retained

- 12 workspaces retained.
- Dashboard backend surface remains **35 authorized commands**.
- No Tauri allowlist expansion was made for cosmetic work.
- NPU → GPU → CPU routing policy was not changed.
- Memory governor behavior was not changed.
- Privacy defaults were not changed.
- Single canonical orb renderer retained.
- No bitmap/video background or framework dependency added.

## Portable validation

- canonical `pytest` with warnings-as-errors: **124 passed**
- product/security audit: **9/9 PASS**
- `python -m compileall -q metatron scripts`: PASS
- `node --check ui/app.js`: PASS
- `node --check ui/orb.js`: PASS
- `node --check ui/orb-renderer.js`: PASS
- theme/settings regression coverage added in `tests/test_ui_theme_upgrade.py`

## Remaining before release-ready

1. Run on Windows from this exact tree:
   - `cargo fmt --check`
   - `cargo check`
   - desktop build / installer inventory
   - DPI/light-theme visual pass
   - orb visibility/bounds probe
   - idle desktop memory benchmark
   - at least 30-minute soak; 60 minutes preferred for final RC
2. Confirm the redesigned shell remains under the existing 500 MiB private-working-set gate and target no more than +40 MiB p95 versus the qualified v1.4 baseline.
3. Re-run the new deterministic primary-work-area orb anchor probe on Windows/DPI combinations.
4. Run the pinned EZSTT protocol/focus/restart/E2E suite and required Metatron placement verification from the release-closure wrapper.
5. Run the now-required Kokoro benchmark for release closure.
6. Optional Phase 6 remains: persisted Home widget show/hide/reorder customization.

This report does **not** claim hardware qualification for the changed UI build.


## Release-closure implementation added after the UI pass

See `RELEASE_CLOSURE_HANDOFF_2026-11-06.md`. Source now includes the pinned single-process EZSTT compatibility adapter, persistent speech-command manifest, automatic EZSTT debug-shell/E2E qualification, deterministic primary-work-area Presence anchoring, required-Kokoro gating and a 60-minute release-closure wrapper. These changes are portably tested but still require target-Windows execution.
