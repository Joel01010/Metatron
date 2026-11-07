# Changelog

## Unreleased — v1.4 self-testing release harness

- Added `TEST-METATRON.cmd` as the normal non-expert full-release entry point plus `TEST-METATRON-QUICK.cmd` for short regressions.
- Added automatic Windows test-machine preparation for Python, Git, Node.js, Rust/MSVC, Visual Studio C++ Build Tools and WebView2, including repair of an existing Visual Studio instance missing the VCTools workload.
- Added an isolated test virtual environment and removed reliance on a human-selected Python interpreter.
- Added automatic Windows ML setup and a generated local ONNX placement probe so no external model path is required.
- Added targeted test wrappers for portable/static, hardware, speech/EZSTT, TTS, Presence/core/pets, Automation Center, packaging and memory/soak qualification.
- Added isolated Presence profiles and automatic Solar/Lattice/Reactor/Pet-only/Both evidence captures without touching the user's real settings database.
- Hardened `Build-Windows.ps1`, support-bundle generation and release closure so they consistently use the prepared interpreter and survive normal Windows PowerShell 5.1 native stderr output.
- Made the top-level runner always emit `SELF-TEST-SUMMARY.json` and an evidence ZIP on PASS or FAIL.
- Expanded the product audit so missing release-test tooling is itself a release-audit failure.
- Portable regression suite is now 148/148 passing; product/security audit remains 9/9 and the dashboard authorization surface remains 35 commands.

## Unreleased — v1.4 full-product completion

- Promoted Presence into a complete configurable product subsystem with Orb / Pet / Both modes and independent desktop/dashboard visibility.
- Added Solar, Lattice and Reactor procedural core geometries with pulse, rotation, complexity, shell, trails and parallax controls while retaining one canonical WebGL renderer.
- Added a validated four-slot companion roster with original Flin/Wisp/Drone/Mote forms, independent skins/behaviors/anchors/colors/size/energy/voice/task reactions and adaptive memory-pressure behavior.
- Made Reduced Motion authoritative for JavaScript companion travel and added a companion-only fallback when WebGL2 cannot initialize.
- Added searchable settings, first-run Presence choice, live core/pet previews, native click-through Presence, deterministic non-resizable sizing and a Windows tray for dashboard recovery, Presence show/hide and quit.
- Added a productized Automation Center for schedules, approvals and persistent agent runs; schedules materialize Ready cards but never silently execute an agent.
- Added explicit run/refresh/cancel lifecycle handling with conservative adapter-specific terminal reconciliation while preserving the 35-command dashboard boundary.
- Added diagnostic checks for Presence/companions and automation stores.
- Extended the native Presence qualification probe to reveal hidden startup without activation and save a supplemental Presence-window screenshot in the one-run evidence bundle.
- Added full-product regression coverage without changing the 2816 MiB Strict managed ceiling or NPU → GPU → CPU routing invariant.

## Unreleased — v1.4 final implementation closure

- Completed the pinned EZSTT integration as a single-process compatibility runtime with verified OpenVINO placement, automatic Parakeet provisioning, active-app privacy enforcement, context/dictionary synchronization and full final-transcript events.
- Privacy-paused speech is blocked before capture, rechecked before injection, and excluded from local history/vocabulary learning.
- Added automatic pinned EZSTT debug-shell build plus protocol/focus/restart/E2E qualification.
- Added Kokoro same-session provisioning and made premium TTS a required final qualification gate.
- Added Home dashboard widget visibility/reordering without changing the 35-command privileged dashboard surface.
- Added Job Object peak commit, system-commit pressure handling, USER/GDI leak telemetry and bounded GPU-counter failure behavior while preserving the 2816 MiB strict managed ceiling.
- Hardened Windows PowerShell native-command execution against stderr-as-error behavior and made the final orchestrator always emit a zipped evidence bundle plus SBOM on PASS or FAIL.
- Preserved deterministic primary-work-area Presence placement and strengthened release regression tests around all previously observed Windows qualification failures.

## Unreleased — v1.4 Spectral UI upgrade candidate

- Added release-closure wiring for the pinned EZSTT engine through a single-process compatibility sidecar with truthful OpenVINO `EXECUTION_DEVICES` placement proof, persistent command manifest discovery and full-transcript events.
- Upgraded EZSTT qualification to auto-build its debug Tauri shell and run protocol/focus/restart/E2E gates.
- Made floating Presence placement deterministic against the primary monitor work area and strengthened the native window probe accordingly.
- Made Kokoro configuration visible in the setup process immediately and added a required-Kokoro release gate.
- Added `Invoke-MetatronReleaseClosure.ps1` for the final Windows hardware/build/E2E/60-minute-soak pass.
- Canonicalized the Windows qualification wrapper to hashtable splatting and made the orb probe launch/clean up the desktop process itself with native NULL class-name marshaling.
- Rebuilt the dashboard visual system around semantic tokens, differentiated materials and the Spectral Presence stage while preserving all 12 workspaces.
- Added five polished theme presets plus Custom: Spectral Rose, Obsidian, Aurora, Ember and Porcelain.
- Added Theme Studio controls for palette, materials, borders, glow, corners, density, font scale, motion and sidebar mode.
- Added safe theme JSON import/export with strict key allowlists, numeric clamping and no raw CSS/HTML/JS path.
- Kept dashboard and floating Presence palettes synchronized through the single canonical orb renderer; added iframe postMessage ingestion, reduced-motion behavior and live orb opacity.
- Preserved the existing 35-command dashboard authorization surface and product/security audit invariants.
- Added UI/theme regression coverage. Hardware/desktop memory qualification still must be rerun on Windows before this candidate is called release-ready.

## 1.4.0 — Hardware qualification and diagnostics hardening

- Added direct OpenVINO NPU/GPU/CPU compile-and-infer verifier using upstream device APIs.
- Added Windows audio endpoint capture smoke testing and TTS interruption verification.
- Added bounded soak/leak qualification with trend analysis.
- Added orb on-screen repositioning and native window visibility/bounds verifier.
- Added installer/signature verification and stronger Windows CI build gates.
- Hardened diagnostics so missing/partial measurements cannot be treated as zero or PASS.
- Version-aligned Python, Tauri, qualification reports and release metadata at 1.4.0.

## 1.3.0 — Professional product layer

### Product
- Added first-run onboarding and Ctrl+K command palette.
- Reworked the dashboard into 12 daily-use workspaces: Home, Dictation, History, Dictionary, Hardware, Models, Voice, Metrics, Tasks, Agents, Diagnostics, Settings.
- Added local dictation history/recovery with search, pin/delete, retention and placement/context metadata.
- Added custom vocabulary with usage ranking and per-app context/privacy rules.
- Added model/runtime readiness center and copyable setup commands.
- Added diagnostics score/checks and full-Windows qualification entry points.

### Runtime and protocol
- Database schema v2 with ordered migrations and pre-upgrade backup.
- Added versioned protocol info and strict JSONL envelope validation.
- Fixed invalid-request correlation so malformed requests retain a valid supplied request ID.
- Added optional speech-sidecar capability contracts for active-app privacy and personalization; unsupported runtimes remain explicitly visible.
- Added history pruning to maintenance.

### Desktop security
- Added explicit Rust-side main-window backend command allowlist; orb remains separately restricted.
- Product audit verifies UI commands are implemented and authorized.
- CSP and single-source orb renderer remain release invariants.

### Qualification
- Added `Test-WindowsPrerequisites.ps1`, `Bootstrap-Windows.ps1`, `Verify-SpeechRuntime.py`, privacy-conscious support bundles and full-system orchestration.
- Added Windows private-working-set / private-bytes / system commit / shared-GPU / 3D-engine sampling.
- Added machine-readable provisional gates in `qualification_thresholds.json` and analyzer tooling.
- CI runs canonical pytest on Windows + Linux and cargo-checks the Windows host.

### Validation
- Portable suite expanded from the v1.2 baseline to 86 pytest cases.
- Product/security audit covers 9 release invariants.
- Linux control-plane benchmark remains well below the 15 ms bridge p95 gate; Windows figures must be measured on a real system.

## 1.2.0 — Hardened core

- Explicit NPU → GPU → CPU routing and placement truth.
- Windows ML same-process provider registration/probe path.
- Async/demultiplex Tauri bridge with bounded push events and 30 Hz latest-wins level coalescing.
- Windows Job Object ownership, DPAPI secret store, environment allowlisting and one-dir packaging.
- Placement-aware memory reservations, accelerator timeouts/cache hooks, cross-vendor inventory merge.
- Procedural reactive orb and isolated TTS / semantic-cleanup workers.


## v1.4.0 re-verification corrections

- fixed checkout-local pytest basetemp and failed-only retention;
- fixed PowerShell desktop-measurement parsing and v1.4 argument forwarding;
- hardened SAPI interruption test and production playback to use asynchronous cancellation;
- made requested memory soak independent of unrelated gate failures;
- made external speech-sidecar absence SKIP unless explicitly required;
- rejected partial process-tree memory totals and preferred private commit for learned worker charges;
- expanded Windows diagnostics with handles, threads, process churn, sampling overhead and commit pressure;
- added memory-hardening and re-verification notes.
