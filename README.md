# Metatron v1.4.0

**Windows-first, local-first desktop intelligence with private dictation, a reactive animated core, optional multi-pet companions, explicit automation and truthful accelerator placement under a strict memory governor.**

Metatron is an open-source Tauri/WebView2 desktop application designed to keep its control plane small while dispatching heavy ML work to disposable sidecars. Its certified core is intentionally narrow: **dictation, reactive presence, memory governance, and truthful NPU → GPU → CPU placement**. The local Kanban/scheduler/approval layer is productized with explicit execution controls. Agent execution adapters and semantic cleanup remain explicitly experimental until their upstream behavior is independently qualified.

## Product principles

- **NPU first, GPU second, CPU last.** Every routable NPU is tried before every routable GPU. CPU is the universal last resort when enabled.
- **Detected is not routable; selected is not actual.** Metatron reports detected, routable, selected, session-created, and verified actual placement separately.
- **Strict memory ownership.** Heavy runtimes are disposable workers; Strict Mode's logical managed ceiling is 2816 MiB.
- **Local and private by default.** Transcript history starts off. Support bundles exclude the SQLite DB, transcript history, audio, and secrets.
- **A real desktop product, not an admin console.** The product layer includes onboarding, command palette, searchable settings, history, dictionary, per-app policies, model center, diagnostics, tray recovery, configurable animated Presence, companions and an explicit Automation Center.

## Product workspaces

Home · Dictation · History · Dictionary · Hardware · Models · Voice · Metrics · Tasks · Agents · Diagnostics · Settings

Presence now supports **Orb / Pet / Both**. The canonical renderer provides Solar, Lattice and Reactor procedural core geometries plus up to four independently configured lightweight companions in the same WebView. User speech drives inward energy; TTS drives outward energy; tasks/runs/approvals create short companion/core reactions. Reduced Motion stops JavaScript pet motion as well as CSS animation, and adaptive mode simplifies companions under memory pressure. High-rate level events use the existing bounded latest-wins channel and stop when no renderer subscribes. See `docs/PRESENCE_AND_COMPANIONS.md`.

## Quick start for developers

```powershell
python -m pip install -e ".[dev]"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -W error -m pytest -q
python scripts\product_audit.py
```

On a full Windows 11 machine, the normal operator path is simply:

```text
Double-click TEST-METATRON.cmd
```

The launcher prepares missing build/test prerequisites when possible, creates an isolated test Python, provisions Windows ML, the pinned EZSTT/Parakeet runtime and Kokoro, builds the product, runs hardware/speech/TTS/Presence/memory gates, and produces one evidence ZIP on PASS or FAIL. See `TESTING.md`. `TEST-METATRON-QUICK.cmd` is available for short code-only regressions but does not replace full Windows qualification.

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

## Tasks and automation

Tasks now include an Automation Center for interval schedules, human approvals and persistent agent-run history. Schedules create **Ready** cards but never silently execute agents; agent execution remains an explicit Run action with manual reconciliation/cancellation. The UI reuses the existing authorized task command contract, so the established 35-command dashboard boundary is not widened. See `docs/AUTOMATION_CENTER.md`.

## Validation status

The source package includes portable regression tests, Windows CI, a product/security audit, core benchmark, accelerator verifier, speech-runtime verifier, Windows process/GPU memory sampler, pinned release gates, privacy-conscious support bundle, and one-command full-system validation.

The release package clearly distinguishes:

- **portable validated** — tests, protocol, product audit, syntax/config, control-plane benchmark;
- **implemented but Windows-required** — Tauri host build, Job Objects, DPAPI, WebView2 desktop behavior;
- **accelerator-gated** — NPU/GPU placement proof, Parakeet latency, power/utilization, hardware-specific model compile/cache behavior.

See `docs/FULL_SYSTEM_VALIDATION.md`, `docs/PRESENCE_AND_COMPANIONS.md`, `docs/AUTOMATION_CENTER.md` and `qualification_thresholds.json`.

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

## v1.4 full Windows qualification

For final Windows qualification, double-click `TEST-METATRON.cmd`. The underlying `scripts/Invoke-MetatronReleaseClosure.ps1` is now self-preparing: it can install/repair the test toolchain, configures Windows ML, generates its own ONNX placement probe, provisions the pinned speech/TTS runtimes, then drives the PowerShell/Rust/Tauri build gates, OpenVINO NPU/GPU/CPU proof, microphone capture, Metatron↔EZSTT placement, pinned EZSTT protocol/focus/restart/E2E, Kokoro benchmarking, deterministic Presence-window placement, full-system memory collection, a 60-minute soak, SBOM generation and installer verification. `Invoke-MetatronV14Qualification.ps1` remains available for narrower diagnostic runs. See `FULL_PRODUCT_HANDOFF_2026-11-07.md` for the current candidate and `RELEASE_CLOSURE_HANDOFF_2026-11-06.md` for the preceding closure baseline.
