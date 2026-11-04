# Metatron v1.3.0

**Windows-first, local-first dictation and desktop intelligence with truthful accelerator placement and a strict memory governor.**

Metatron is an open-source Tauri/WebView2 desktop application designed to keep its control plane small while dispatching heavy ML work to disposable sidecars. Its certified core is intentionally narrow: **dictation, reactive presence, memory governance, and truthful NPU → GPU → CPU placement**. Agent adapters, scheduler automation, and semantic cleanup are available but remain explicitly experimental.

## Product principles

- **NPU first, GPU second, CPU last.** Every routable NPU is tried before every routable GPU. CPU is the universal last resort when enabled.
- **Detected is not routable; selected is not actual.** Metatron reports detected, routable, selected, session-created, and verified actual placement separately.
- **Strict memory ownership.** Heavy runtimes are disposable workers; Strict Mode's logical managed ceiling is 2816 MiB.
- **Local and private by default.** Transcript history starts off. Support bundles exclude the SQLite DB, transcript history, audio, and secrets.
- **A real desktop product, not an admin console.** v1.3 adds onboarding, command palette, history, dictionary, per-app policies, model center, diagnostics, and full-system qualification tooling.

## v1.3 workspaces

Home · Dictation · History · Dictionary · Hardware · Models · Voice · Metrics · Tasks · Agents · Diagnostics · Settings

The UI keeps the pale-red/golden procedural orb as Metatron's presence. User speech drives inward energy; TTS drives outward energy. High-rate level events are pushed through a bounded latest-wins channel at ~30 Hz and stop when no renderer subscribes.

## Quick start for developers

```powershell
python -m pip install -e ".[dev]"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -W error -m pytest -q
python scripts\product_audit.py
```

On a full Windows 11 machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Test-WindowsPrerequisites.ps1 -RequireDevTools
powershell -ExecutionPolicy Bypass -File .\scripts\Bootstrap-Windows.ps1 -AllRuntimes -Build -Validate
```

The runtime root defaults to `%LOCALAPPDATA%\Metatron`. No optional runtime/model is installed unless the corresponding setup switch is supplied.

## Hardware routing

Metatron's routing invariant is:

```text
all routable NPUs → all routable GPUs → CPU
```

Windows ML support is vendor-neutral by hardware class. Direct OpenVINO remains available for Intel systems. Metatron does not claim accelerator placement merely because a provider appears in a list: real certification requires session creation, warm-up, CPU fallback disable where supported, runtime execution-device evidence, and Windows utilization cross-checks.

## Dictation and personalization

The product layer includes:

- local dictation history with search, pin/delete, retention, app/context/placement metadata;
- local custom vocabulary with case-insensitive terms and usage ranking;
- per-app context/privacy rules (`allow`, `no_context`, `pause`);
- optional runtime capability contracts for foreground-app privacy enforcement and vocabulary/context synchronization;
- UIPI/injection failure reporting rather than false success;
- hotkey/button barge-in while echo guard suspends capture.

If a speech sidecar does not implement `active_app`, `set_app_policy`, or `set_personalization`, the UI reports the feature as **policy-only / local-only** rather than pretending it is enforced.

## Voice

TTS stays outside the core process. Premium mode targets Kokoro; light mode can use Piper/Windows voice fallback. TTS speaks important system replies by default and can be disabled completely. The orb reacts to real TTS level events.

## Validation status

The source package includes portable regression tests, Windows CI, a product/security audit, core benchmark, accelerator verifier, speech-runtime verifier, Windows process/GPU memory sampler, pinned release gates, privacy-conscious support bundle, and one-command full-system validation.

The release package clearly distinguishes:

- **portable validated** — tests, protocol, product audit, syntax/config, control-plane benchmark;
- **implemented but Windows-required** — Tauri host build, Job Objects, DPAPI, WebView2 desktop behavior;
- **accelerator-gated** — NPU/GPU placement proof, Parakeet latency, power/utilization, hardware-specific model compile/cache behavior.

See `docs/FULL_SYSTEM_VALIDATION.md` and `qualification_thresholds.json`.

## Repository map

```text
metatron/              Python control plane
  core.py              application composition / lifecycle
  memory.py            managed memory broker
  hardware.py          inventory, routing and placement records
  speech.py            disposable speech sidecar client
  tts.py               TTS manager/providers
  cleanup.py           deterministic + optional semantic cleanup
  productivity.py      history, vocabulary and app rules
  diagnostics.py       readiness/runtime inventory
ui/                    dependency-light WebView2 frontend + orb shader
src-tauri/             Rust host, window boundaries, bridge, Job Object owner
scripts/               setup, verification, benchmark, packaging tools
tests/                 canonical pytest suite
docs/                  architecture, policy, validation, release docs
```

## Security model

- CSP is enabled.
- Main and orb windows are scoped separately.
- Rust enforces a command allowlist for the dashboard; the orb gets a much smaller allowlist.
- Managed local HTTP services are loopback-only and use per-launch credentials where supported.
- Child environments are allowlisted; arbitrary API-key variables are not inherited.
- Windows secrets use a DPAPI-backed implementation; tests use an in-memory fake.
- Managed subprocesses are intended to live under a Windows Job Object with `KILL_ON_JOB_CLOSE`.

See `SECURITY.md` and `docs/PRIVACY_AND_HISTORY.md`.

## License

Metatron source is MIT licensed. Optional models/runtimes keep their own licenses and are not automatically redistributed by this repository. See `THIRD_PARTY.md`, `docs/LICENSE_GATE.md`, and `models.lock.json` before publishing a binary/model bundle.
