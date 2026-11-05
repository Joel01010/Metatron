# Metatron v1.4.0 — Corrected Source, Verification and Remaining Gates

Date: 2026-11-04

## Status

This package is **portable-test-vetted, not Windows-hardware-certified**. It is a corrected release candidate derived from the user's uploaded `Metatron_OpenSource_v1.3_Professional` archive, not a claim that unavailable Windows hardware was tested. Do **not** publish it as production-certified until the remaining qualification gates have real evidence.

## Fixes in this package

- Align `src-tauri/Cargo.toml` to 1.3.0.
- Include proper icon files and a nonempty `src-tauri/resources` directory to unblock Tauri bundling.
- Avoid unconditional unsafe `Send/Sync` raw HANDLE implementation: represent owned job handle as integer, restrict access to creation and Drop, and terminate/reap a spawned backend if assignment fails.
- Explicitly show the separate floating orb on startup and enforce its always-on-top state (Windows visual placement still needs checking).
- Correct Windows UTF-8 test and product-audit handling, exclude build artifacts from product scan.
- Fix PowerShell harness command argument shadowing of `$args`, and native stderr handling.
- Repair PowerShell `throw` syntax and avoid reserved `$PID` as a parameter name.
- Make GPU metrics polling bounded with a separate process/job, report unavailable GPU data as `null`, and allow `-SkipGpu`. Failure to collect data must never be reported as zero utilization.
- Keep loop cadence best effort while accounting for counter collection time.
- Prevent incomplete memory qualification from passing: missing process metrics, absent samples, or missing baseline system commit delta fail certification.
- Cache slow agent-discovery queries briefly without caching OpenCode server readiness in start/submit paths.
- Copy PyInstaller backend resources into the release executable's resource directory for standalone direct launches.
- Add regression tests for no-data false passes, GPU unknown state, memory commit evidence, Windows script contracts, and OpenCode cache.

## Verification completed in Linux container

- Canonical `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -W error -m pytest -q`: see final verification log.
- `python -m unittest discover -s tests -q`: see final verification log.
- Python syntax compile (`compileall`): see final verification log.
- Node syntax checks of all 3 UI JavaScript files: see final verification log.
- Product audit: see audit.json.
- 100-sample live JSONL backend benchmark: see benchmark.json.
- CI YAML parses; Tauri JSON parses: see final verification log.
- Clean extraction of deliverable zip tested separately: see final verification log.

## Windows and hardware work that cannot honestly be completed here

- `cargo check`, Tauri compile, MSI/NSIS installer build, real WebView2 rendering and orb cross-monitor/DPI placement.
- Real Intel NPU 3720 inference, GPU fallback, CPU last-resort fallback and verified provider execution.
- Actual Parakeet / EZSTT / Kokoro runtime and audio input/output: model/engine assets absent.
- Windows PowerShell `Get-Counter`, job timeout behavior and host process-tree counters.
- DPAPI and Windows owned-worker termination proof, signed installer and updater behavior.
- Full 2–3 GiB memory, GPU utilization and speech timing gates on the target laptop.

## On-device checks required before declaring complete

1. Work on a fresh copy of this patched archive; do not overwrite the existing Z: checkout before comparison/backup.
2. Use configured Z: Python virtual environment and Cargo home; **do not use system Python for installs**.
3. Run `python -W error -m pytest -q` and `python scripts/product_audit.py`; ensure zero errors.
4. Run `cargo check` inside `src-tauri`; build with `scripts/Build-Windows.ps1` using explicit `-Python` and `-BuildVenv` arguments.
5. Run `scripts/Invoke-MetatronFullValidation.ps1` with proper Python and output directory. Preserve machine report and logs.
6. Run `scripts/Measure-MetatronDesktop.ps1` for `idle_shell` and `certified_core`. If GPU counters fail, use `-SkipGpu`, **mark GPU gate UNVERIFIED**, and separately diagnose the driver/counter provider.
7. Confirm the orb is visible and correctly positioned on all connected monitors and screen scales; test show/hide, always-on-top, motion and GPU load.
8. Provision and verify the pinned audio models and speech runtime following license review; run real microphone, audio-focus, barge-in and NPU/GPU/CPU placement tests.
9. Verify Windows process ownership/kill-on-job-close, DPAPI, installer launch/uninstall, signing and real memory delta.

Do not mark any hardware-gated item PASS based on static tests or synthetic JSON. The previous handover was already explicit about this distinction.
