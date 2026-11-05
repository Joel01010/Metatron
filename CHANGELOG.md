# Changelog

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
