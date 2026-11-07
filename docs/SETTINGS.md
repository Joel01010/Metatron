# Settings

Settings are stored under the `app.settings` key in SQLite and merged with safe defaults.

## Appearance

Theme Studio uses the existing `appearance` settings section; it does not create a second configuration store.

- preset theme: Spectral Rose, Obsidian, Aurora, Ember, Porcelain, or Custom
- accent and intelligence/core colors
- background and surface tint
- material, border and glow strength
- corner-radius family
- font scale
- compact / comfortable / spacious density
- minimal / balanced / expressive motion
- full / compact sidebar
- reduced motion

The legacy `metatron` theme ID is still accepted and maps visually to Spectral Rose. Imported theme JSON is allowlisted and cannot contain raw CSS, HTML or JavaScript. Numeric values are clamped by the importer and validated again by the settings backend.

## Presence

- master Presence enabled switch
- Orb / Pet / Both mode
- Eco / Balanced / Spectacle quality
- independent desktop/dashboard orb visibility
- independent desktop/dashboard companion visibility
- always-on-top, click-through and scale / opacity
- Solar / Lattice / Reactor procedural core geometry
- core pulse / rotation / complexity / shell
- plasma / particles / bloom / trails / parallax / interaction gain

## Companions

The companion roster is stored in the validated `companions` section and supports at most four entries. Each pet has independent name, enabled state, original procedural form, skin, behavior, anchor, two colors, size, energy, voice reactivity and task reactivity. Global settings control reaction gain, pointer interaction and `adaptive` / `full` / `minimal` performance policy.

Public builds include no copyrighted character art. Reduced Motion also disables JavaScript companion travel, not just CSS animation.

## Voice

- TTS enabled
- premium / light / off
- voice ID
- speed
- system-reply priority threshold
- echo guard
- barge-in
- cleanup toggle

## Hardware

- device order
- CPU fallback
- visual reduction during inference pressure
- low-power preference

## Memory

- Strict / Voice / Agent profile
- adaptive system-pressure handling

## Privacy

- local-only telemetry
- transcript persistence
- audio persistence
- cloud-context default

## Agents

- confirmation before local launches
- confirmation before cloud launches
- automatic Kanban card creation
- local coding-agent concurrency
