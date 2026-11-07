# Presence, animated core and companions

Metatron v1.4 keeps **one Presence WebView** and one canonical renderer source (`ui/orb-renderer.js`). The serious system presence and the optional companion layer share that surface; companions do not create extra renderer processes or WebViews.

## Presence modes

The `presence.mode` setting is one of:

- `orb` — animated core only;
- `pet` — companions only;
- `both` — core and companions together.

Desktop and dashboard visibility are independent for the orb and companions. Desktop Presence can also be made **click-through**, which asks the native Tauri window to ignore cursor events; the tray remains the recovery/control surface. `presence.enabled` is the master switch. The native Presence window starts hidden and is revealed after persisted settings load, which prevents a startup flash and makes saved visibility authoritative from the first visible frame.

## Animated core

Three procedural shader geometries are built in:

- **Solar** — luminous singularity with plasma shell;
- **Lattice** — geometric energy lattice and arcs;
- **Reactor** — concentric ring/spine reactor structure.

Core behavior can be tuned independently with pulse, rotation, complexity, shell strength, trails, parallax, plasma, particles, bloom, scale, opacity and interaction gain. Speech input drives inward/user energy; thinking and TTS drive the assistant side; task/run/approval events create short signal reactions.

Eco/Balanced/Spectacle quality remains the renderer-performance contract. The renderer is still a single logical presence resource in the memory broker. Multiple pets do not multiply the WebView or WebGL contexts.

If WebGL2 cannot initialize, Metatron does **not** create a second renderer. The canvas is disabled and the same Presence document falls back to lightweight, static companion rendering. This makes Pet mode usable on a machine where the 3D core is unavailable.

## Companion roster

Metatron ships four original procedural forms. They are UI primitives, not third-party/copyrighted character artwork:

| Companion | Form | Default behavior | Purpose |
|---|---|---|---|
| Flin | soft spectral creature | orbit | general presence |
| Wisp | luminous energy wisp | drift | quiet ambient companion |
| Drone | compact graphite drone | perch | task/run reactions |
| Mote | small energy mote | pointer | highly reactive pointer/voice companion |

The roster supports **up to four simultaneous companion configurations**. Each entry has independent:

- name and enabled state;
- form and skin;
- orbit / drift / perch / pointer-follow behavior;
- free or corner anchor;
- primary and secondary colors;
- size and energy;
- voice reaction and task reaction gains.

The backend validates the complete roster before persistence: maximum four entries, unique safe IDs, bounded names, known forms/skins/behaviors/anchors, `#RRGGBB` colors and bounded numeric fields.

## Performance and accessibility

`companions.performance_policy` is:

- `full` — render every enabled pet;
- `adaptive` — render the full roster normally, but collapse to one companion during Eco mode or recent memory pressure;
- `minimal` — render at most one companion.

Reduced Motion is authoritative for JavaScript movement as well as CSS animation. In reduced/minimal motion, companions use stable deterministic positions instead of orbiting, drifting or following the pointer.

The pointer-interaction switch disables pointer following globally without changing each pet's stored behavior.

## First run and recovery

Onboarding asks the user to choose Orb, Pets, or Both. Choosing a pet mode enables the companion subsystem and the first companion so the selection produces a visible result immediately.

The Windows tray provides:

- Open Dashboard;
- Show / Hide Presence;
- Quit Metatron.

Closing the main dashboard hides it instead of leaving a background Presence window with no recovery surface.

## Qualification evidence

`Test-OrbWindow.ps1` finds the native Presence window, reveals it without activation for qualification, verifies the deterministic primary-work-area anchor and can save a PNG of the Presence window. The screenshot is supplemental evidence; placement pass/fail remains native and numeric.
