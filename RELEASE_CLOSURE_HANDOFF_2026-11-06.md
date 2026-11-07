# Metatron v1.4 Spectral UI — Release-Closure Handoff

Date: 2026-11-06  
Status: **portable closure checks PASS; target-Windows requalification required**

## What this pass closes in source

### Metatron ↔ EZSTT wiring

- The speech runtime is pinned to upstream EZSTT revision `5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a`.
- `scripts/ezstt_metatron_sidecar.py` is a thin **single-process** compatibility entrypoint. It imports the pinned EZSTT engine in-process; it does not proxy to or keep a second resident STT engine.
- Metatron-only configuration metadata is filtered before native EZSTT `set_config`, while truly unknown fields are rejected.
- Placement is considered verified only when the requested class matches both the active transcriber's device and OpenVINO `EXECUTION_DEVICES` from the compiled Parakeet encoder. Requested-device strings alone are not proof.
- Cold compile/warm-up is allowed up to the bounded Metatron placement timeout before fallback.
- The adapter wraps EZSTT's existing injection function so the complete successful final transcript is also emitted into Metatron's local event/history path; EZSTT still performs the actual focused-window injection.
- `Setup-SpeechRuntime.ps1` installs the adapter next to the pinned engine and writes `%LOCALAPPDATA%\Metatron\runtimes\speech-command.json`. `METATRON_SPEECH_CMD` remains the higher-precedence override.
- Metatron reads that manifest on normal Windows desktop launches, so speech configuration no longer depends on inheriting the setup shell's environment.
- The UI now exposes only the pinned runtime's supported Hold/Toggle modes.

The pinned EZSTT protocol still does not implement Metatron's optional runtime dictionary injection or per-app pause/context-policy channel. The adapter reports those capabilities as unsupported rather than pretending they are enforced.

### EZSTT upstream E2E gate

`Invoke-EZSTTQualification.ps1` now builds the pinned debug Tauri shell automatically when missing using:

```powershell
npm ci
npm run tauri build -- --debug --no-bundle
```

It then runs, in order:

1. `test_protocol.py`
2. `test_focus.py`
3. `test_restart.py`
4. `test_e2e.py`

This directly closes the old automation gap where protocol qualification passed but focus/restart/E2E stopped because `src-tauri\target\debug\ezstt.exe` had not been built.

### Kokoro qualification

- `Setup-Kokoro-TTS.ps1` now sets the Kokoro environment in the **current PowerShell process** as well as future user sessions, so setup followed immediately by validation no longer produces a false “not configured” skip.
- Full validation adds `-RequireKokoro`; when used, a missing or failing premium Kokoro runtime is a release failure instead of a SKIP/WARN.

### Deterministic Presence placement

- The floating Presence window now anchors to the bottom-right of the **primary monitor work area**, 24 physical pixels inside the usable desktop, rather than the full monitor panel.
- Resizing the native orb window re-applies the anchor.
- `Test-OrbWindow.ps1` now validates visibility, monitor intersection, and the deterministic primary-work-area anchor with a DPI-tolerant margin check.

### Release-closure orchestration

A new wrapper, `scripts/Invoke-MetatronReleaseClosure.ps1`, runs the existing canonical v1.4 qualification path with:

- qualification runtime setup;
- hardware-required validation;
- Rust fmt + cargo check when the Windows toolchain is present;
- full desktop build and artifact inventory;
- real accelerator and microphone gates;
- required Metatron↔EZSTT placement;
- required Kokoro benchmark;
- deterministic orb probe;
- idle desktop benchmark;
- pinned EZSTT protocol/focus/restart/E2E;
- **60-minute soak by default**;
- support bundle/evidence generation through the existing full-validation path.

Authenticode remains optional in the wrapper because a valid signing certificate is an external credential. Add `-RequireSigned` only after signing is configured.

## Portable evidence from this exact tree

- canonical pytest with warnings-as-errors: **124 passed**
- product/security audit: **9/9 PASS**
- dashboard backend authorization surface: **35 commands, unchanged**
- Python `compileall`: PASS
- `node --check ui/app.js`: PASS
- `node --check ui/orb.js`: PASS
- `node --check ui/orb-renderer.js`: PASS
- single canonical orb renderer: retained
- Strict memory admission ceiling: **2816 MiB, unchanged**

Rust/PowerShell/Windows desktop execution is not available in the Linux packaging environment, so this document does not claim Windows PASS for the changed tree.

## Prior Windows baseline vs this candidate

The earlier v1.4 Windows baseline already produced real OpenVINO NPU/GPU/CPU execution proof, real microphone capture, SAPI interruption evidence, a successful 60-minute soak and a standalone orb pass. Those results are useful regression baselines, **not** substitute evidence for the Spectral UI/closure tree. The UI/WebView and speech integration changes require a fresh run.

## Exact target-Windows run

If the already-qualified pinned EZSTT model/runtime and Kokoro assets are still installed:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Invoke-MetatronReleaseClosure.ps1 `
  -Python python
```

To refresh the runtime wiring/assets first:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Invoke-MetatronReleaseClosure.ps1 `
  -Python python `
  -PrepareSpeech `
  -PrepareKokoro
```

`-PrepareSpeech` intentionally verifies the integration and therefore requires the Parakeet model to exist under the pinned EZSTT runtime. It does not silently download a large speech model.

For a signed release candidate, sign the Windows artifacts and rerun with `-RequireSigned`.

## Still external or intentionally unresolved

1. **Windows requalification:** must run on the reference Core Ultra/Intel graphics system for this exact tree.
2. **Authenticode:** requires the user's signing certificate/private key; no certificate is embedded or fabricated.
3. **GPU performance counters:** Windows GPU counter availability can remain incomplete. OpenVINO execution-device proof is the placement authority; missing perf counters must remain WARN/unknown, never fake zero/PASS.
4. **Pinned EZSTT optional capabilities:** runtime dictionary injection and per-app pause/context enforcement remain explicitly unsupported by upstream and are surfaced as such.
5. **Widget show/hide/reorder:** still an optional product phase, not a release-closure prerequisite.
