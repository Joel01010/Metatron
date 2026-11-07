# Metatron v1.4 — Full Product Completion Handoff

Date: 2026-11-07
Candidate lineage: `Metatron_v1.4_Final_Implementation_Candidate.zip` → full-product completion pass

## Verdict

This tree closes the remaining **code-level product work** identified in the v1.4 UI/release-closure sequence while preserving the previously hardened control plane. The new work is primarily product-layer functionality: animated Presence, multi-companion behavior/settings, desktop lifecycle, searchable onboarding/settings, and explicit task automation/run controls.

This package is **portable-validated, not newly Windows-qualified**. The prior target-machine reports already established the reference Core Ultra 7 155H host, OpenVINO NPU/GPU/CPU execution, microphone capture, desktop idle budget and 60-minute soak. Because this candidate changes WebView2 rendering, native tray/window behavior and Rust host code, the one-command Windows closure must be rerun before calling this exact ZIP release-qualified.

## Full-product additions

### Presence and animated core

- One canonical Presence renderer and one Presence WebView remain the architecture invariant.
- Orb / Pet / Both master mode.
- Solar / Lattice / Reactor procedural core geometry.
- Independent core pulse, rotation, complexity, shell, trails and parallax.
- Existing plasma, particles, bloom, opacity, scale and interaction gain retained.
- Independent desktop/dashboard orb visibility.
- Native always-on-top and click-through controls.
- Presence native window starts hidden until persisted settings load, then is revealed only if the chosen Orb/Pet/Both policy requires it.
- Deterministic primary-monitor work-area anchoring is retained.
- Presence window is non-resizable; product Scale is the single sizing control.
- Companion-only graceful fallback if WebGL2 cannot initialize.
- Reduced Motion now stops JavaScript companion travel as well as CSS animation.

### Multiple companions / pets

Four original procedural companion slots are built in:

1. Flin
2. Wisp
3. Drone
4. Mote

Each slot independently stores and validates:

- name and enabled state;
- form and skin;
- orbit / drift / perch / pointer behavior;
- anchor;
- two colors;
- size and energy;
- voice reactivity;
- task reactivity.

Global companion settings include enable, reaction gain, pointer interaction and Full / Adaptive / Minimal performance policy. Adaptive mode collapses to one visible pet during Eco quality or recent memory pressure rather than spawning/removing WebViews.

A safe read-time migration maps the old `presence.pet_enabled` setting to Both mode + the first companion. Only recognized built-in legacy skin names are mapped; arbitrary legacy asset paths are never imported.

### Desktop lifecycle

- System tray: Open Dashboard / Show-Hide Presence / Quit.
- Closing the dashboard hides it instead of stranding a background Presence process with no recovery UI.
- First-run onboarding now chooses Orb / Pets / Both.
- Settings search was added for the expanded configuration surface.
- Live preview controls exercise listening, speaking and task reactions.

### Tasks and Automation Center

The Tasks workspace now includes:

- task composer with optional agent assignment;
- interval schedule creation;
- pause / resume / delete schedules;
- pending approval decisions;
- persistent run history;
- explicit Run on an assigned Ready card;
- manual Refresh and Cancel for running work.

A schedule **only materializes a Ready card**. It never silently launches an agent. Agent execution remains explicit and auditable.

Run reconciliation is conservative:

- Claude Code: result state;
- E.O.P./Ezra: job state;
- OpenCode: session state;
- Codex: explicit terminal turn events only.

Success moves the card to Review, failure to Blocked, cancellation to Backlog.

The product reuses the existing dashboard-safe `tasks.list`, `tasks.create` and `tasks.move` commands. The Rust main-window allowlist remains **35 commands**.

## Invariants preserved

- Strict managed ceiling: **2816 MiB**.
- Device-class order: **all routable NPUs → all routable GPUs → optional CPU**.
- Requested placement is never reported as verified without runtime evidence.
- Single canonical orb renderer.
- Heavy ML workers remain disposable/out-of-process.
- Local telemetry and opt-in transcript/cloud context policy unchanged.
- Persistent secrets remain outside ordinary SQLite.
- Dashboard privileged command count remains 35.
- No copyrighted pet/character assets are bundled.

## Portable validation performed in this pass

- **148 pytest tests collected and passed** with warnings treated as errors.
- New full-product regression module covers:
  - three core styles and dynamics validation;
  - four-pet schema and independent configuration;
  - legacy single-pet migration safety;
  - schedule pause/resume/delete;
  - scheduled Ready-card materialization without auto-execution;
  - explicit agent-run persistence and terminal reconciliation;
  - tray/hidden Presence/click-through/native sizing contracts;
  - unchanged 35-command dashboard authorization;
  - WebGL companion fallback and Reduced Motion contract.
- Product/security audit: **9/9 PASS**.
- UI JS syntax: app / orb bridge / orb renderer PASS.
- Python compileall PASS.
- Portable control-plane benchmark: **~0.8693 ms command p95** against the 15 ms provisional bridge gate.

Rust/Tauri compilation and PowerShell execution cannot be performed in the current Linux build container. Current Tauri 2 documentation was checked against the tray and cursor-ignore APIs used here, but the canonical Windows `cargo fmt --check`, `cargo check` and desktop build remain mandatory.

## Previous hardware evidence used as regression baseline

From the supplied Windows qualification materials for the same v1.4 line:

- Core Ultra 7 155H / Intel AI Boost NPU / Intel Graphics reference host.
- OpenVINO NPU/GPU/CPU proof passed.
- Real 16 kHz microphone capture passed.
- SAPI interruption was subsequently tightened and passed at 36.4 ms.
- Desktop idle private working set p95: 371.9 MiB (under 500 MiB gate).
- 60-minute soak passed; private-bytes slope +18.0 MiB/h (under 64 MiB/h gate).
- Prior missing EZSTT focus/restart/E2E, deterministic orb positioning and Kokoro wiring were already closed by the preceding Final Implementation Candidate and are retained here.

These results are evidence for the hardware architecture and thresholds, **not a substitute for re-running this changed full-product tree**.

## One target-machine run

From the extracted candidate root, **double-click `TEST-METATRON.cmd`**. No local agent or operator has to select a Python environment, model path, Windows ML runtime, speech command or TTS command.

The launcher prepares missing build/test prerequisites when possible, creates an isolated test environment, provisions Windows ML and an automatic ONNX probe, then provisions/repairs the pinned speech and Kokoro runtimes, drives the deterministic portable/Rust/PowerShell/build/hardware/STT/TTS/EZSTT/orb/desktop gates, performs the default 60-minute soak, emits an SBOM and creates one zipped evidence bundle on either PASS or FAIL.

The Presence gate now also writes `presence-window.png` as supplemental visual evidence. The screenshot does not decide pass/fail; native visibility/bounds/anchor checks do.

Use `-RequireSigned` only when a real Authenticode certificate/private key is available. Signing is the remaining publication credential dependency, not missing source implementation.

## Relevant product docs

- `docs/PRESENCE_AND_COMPANIONS.md`
- `docs/AUTOMATION_CENTER.md`
- `docs/UI_THEME_STUDIO.md`
- `docs/FULL_SYSTEM_VALIDATION.md`
- `docs/MEMORY_POLICY.md`
- `docs/PRIVACY_AND_HISTORY.md`
- `RELEASE_CHECKLIST.md`
