# Metatron v1.2 implementation and validation status

This release applies the amended technical-review work order while keeping hardware-dependent claims explicit.

## Implemented

- Canonical pytest CI on Windows and Linux; Windows Rust/Tauri job.
- SQLite `PRAGMA user_version` migrations with pre-upgrade backups.
- Strict settings validation and fixed NPU -> GPU -> CPU class policy.
- Portable `%LOCALAPPDATA%\\Metatron` defaults; no hard-coded `Z:` root.
- PyInstaller one-dir staging.
- Async/demultiplexed Tauri backend bridge, stderr drain, UTF-8 Python, structured argv.
- Push events with latest-wins ~30 Hz coalescing and visibility subscriptions; polling retained only as debug/compatibility API.
- CSP and per-window command restrictions; orb window cannot invoke agent/secrets/settings mutation commands.
- Windows DPAPI secret store interface plus in-memory fake; child environment allowlisting.
- Windows Job Objects for Python-owned workers and Rust-owned backend (`KILL_ON_JOB_CLOSE`), without commit caps.
- One canonical procedural orb renderer source.
- Placement-aware model reservations, worst-case admission before actual placement.
- Cross-vendor routable device merge from isolated Windows ML runtime.
- Same-process Windows ML ensure/register/session/warm-up probe with CPU EP fallback disabled for NPU/GPU claims.
- Test-only hardware fault injection; no production environment/IPC switch.
- Per-attempt STT NPU -> GPU -> CPU retry with placement-mismatch rejection.
- Configurable compile/load attempt timeouts and OpenVINO cache hooks in verification worker.
- Privacy-conscious accelerator JSON report + community compatibility issue template.
- Parameterized speech runtime setup; S1-mini worker adapter, setup script and contention stand-in.
- Memory metric definitions and Windows metric collector.
- Model license gate document.

## Portable validation performed in the build environment

Run `python -m pytest -q`, `python -m compileall -q metatron scripts tests`, frontend `node --check`, and Tauri JSON parsing. `scripts/benchmark_core.py` records control-plane round-trip latency and process-tree working set.

## Hardware/Windows validation still required

The build environment is Linux and has no Rust toolchain, Windows APIs, NPU/GPU drivers, WebView2 or audio devices. Therefore the following are implemented but not proven here:

- Rust/Tauri compilation and packaging.
- Windows Job Object and DPAPI behavior.
- Windows ML EP registration/session creation on Intel/AMD/Qualcomm hardware.
- Actual NPU/GPU/CPU inference placement and PDH utilization correlation.
- STT microphone/hotkey/UIPI path and final latency.
- WebView2 orb GPU utilization and dual-window memory delta.
- TTS playback/barge-in timing.
- power/battery measurements.

A release must not convert those items into "validated" until the Windows evidence bundle exists.
