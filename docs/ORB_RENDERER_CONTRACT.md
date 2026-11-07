# Metatron Procedural Orb Renderer Contract

The frontend renders a genuinely dimensional pale-red / golden-core presence in the single canonical WebGL2 renderer. Do not use a looping video/GIF as the primary orb and do not create a second renderer for companions.

## Suggested layers

1. Gold singularity/core sphere.
2. Inner turbulent plasma/noise volume.
3. Rotating gold filaments/rings.
4. Refractive energy membrane.
5. Pale-red translucent spectral shell.
6. Sparse 3D particle field.
7. Corona/halo.
8. Bloom and restrained lens effects.

## State semantics

- `idle`: slow breathing shell + weak gold heartbeat.
- `listening`: incoming/inward particle field; microphone amplitude drives shell displacement.
- `transcribing`: tighter rotating rings, reduced particle noise.
- `thinking`: gold core contracts/intensifies; filaments accelerate inward.
- `speaking`: outward shock waves driven by `tts.level`; gold core radiates into pale-red shell.
- `approval`: temporary gold vertical flare/ring.
- `error`: short instability/crackle effect; do not use constant red flashing.

## Quality profiles

- `eco`: 15 FPS idle / 30 active, low particles, half-res bloom. Backend estimate 90 MiB.
- `balanced`: 24 FPS idle / 60 active, medium particles, dynamic bloom. Estimate 180 MiB.
- `spectacle`: 30 FPS idle / 60 active, dense particles and enhanced volumetrics. Estimate 280 MiB.

When `presence.context.dashboard_open=true`, dashboard orb is primary and floating desktop orb should fall to reduced/eco rendering. The backend reserves one logical presence budget and accepts measured RSS through `memory.measured`.

## v1.4 full-product core geometry

The renderer exposes three procedural core forms: Solar, Lattice and Reactor. They share the same state/level contract and are parameterized by pulse, rotation, complexity, shell, trail and parallax controls.

## Companion layer

Companions are lightweight DOM/CSS procedural forms inside the same Presence WebView. The renderer supports at most four active configurations and reacts to speech, TTS, task/run/approval and memory-pressure events. Adaptive policy collapses to one visible companion in Eco/recent pressure. Reduced Motion uses deterministic static positions.

If WebGL2 initialization fails, the canvas is disabled and the same document can continue in companion-only fallback mode; no alternate GPU renderer or process is spawned.
