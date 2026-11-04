# Metatron v0.4 Memory Budget

## Hard rule

Default target: **2–3 GiB for the Metatron-managed platform**, with Strict Mode capped at **2816 MiB logically reserved**.

The control plane itself remains around ~100 MiB in the Linux validation environment. Windows 11 measurements on the target laptop replace provisional estimates.

## Priority order

1. STT / microphone path
2. Metatron core
3. Presence orb
4. Active user-facing coding task
5. Dashboard
6. Premium TTS while actively speaking
7. S1-mini cleanup
8. Optional/experimental models

A 9B local assistant is not admitted in Strict Mode.

## Memory techniques

- One STT model at a time.
- Heavy ML libraries never import into the Metatron core.
- Kokoro and cleanup are disposable child workers.
- TTS and S1-mini are expected to time-share RAM.
- Codex/OpenCode are lazy; Claude Code is transient.
- Ezra is remote and consumes negligible local runtime memory.
- Telemetry is batched.
- High-rate orb/audio events are RAM-only in a bounded ring.
- The orb uses one procedural shader with no image/video assets or Three.js dependency.
- Renderer resolution/FPS scales by Eco/Balanced/Spectacle mode.
- Dashboard and floating orb never both need full spectacle rendering.
- Process-tree RSS, not parent-process RSS, drives real accounting.
- Eviction calls actual teardown hooks.
- The memory broker is thread-safe.

## System-pressure guard

Every telemetry interval Metatron checks OS-level available RAM. If it falls below the active profile's safety floor, Metatron:

1. unloads S1-mini if resident;
2. unloads idle TTS workers;
3. downgrades the orb to Eco;
4. emits `memory.pressure` for the UI;
5. does not auto-restore resources later, avoiding oscillation.

The dashboard may choose to react to `memory.pressure` by destroying secondary WebViews or reducing chart sampling.

## Strict provisional reservations

| Resource | MiB | Policy |
|---|---:|---|
| Core target | 160 | fixed |
| Pet/overlay base | 64 | fixed |
| Headroom | 224 | protected |
| Orb Eco / Balanced / Spectacle | 90 / 180 / 280 | adaptive |
| Dashboard | 260 | only while open |
| Parakeet Unified | 1050 | highest priority |
| S1-mini | 560 | lazy, 45 s unload |
| Kokoro FP16 | 330 provisional | lazy; measured later |
| Kokoro INT8 | 260 provisional | compact option |
| Piper | 150 | one-shot |
| Windows SAPI | 90 | one-shot fallback |
| Codex | 180 | lazy, measured |
| Claude Code | 220 | transient |
| OpenCode | 240 | lazy, measured |

## Boundary

Metatron can only guarantee memory release for runtimes it owns or that expose a working teardown hook. Externally started E.O.P. remains external until host-level process telemetry is added to E.O.P. itself.
