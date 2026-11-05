# Metatron v1.4.0 — Automated Diagnostics Toolkit

This source package adds diagnostic utilities to the portable-test-vetted corrected release candidate.

## Added
- `scripts/Invoke-MetatronDiagnostics.ps1`: Windows launcher, optional native PID telemetry, opt-in crash-event summaries and redacted bundle.
- `scripts/diagnostics/run_diagnostics.py`: bounded automated Python, JS, product audit and benchmark checks.
- `scripts/diagnostics/process_sampler.py`: cross-platform process-tree RSS/USS, CPU, I/O, threads, handles and availability telemetry with root PID identity verification.
- `scripts/diagnostics/analyze_telemetry.py`: p50/p95/peak summaries, missing-data flags and baseline comparisons, supporting native Windows JSON and portable JSONL.
- `tests/test_diagnostics_toolkit.py`: eight diagnostic regression tests.
- `docs/DIAGNOSTICS_PLAYBOOK.md`: runbook, experiment matrix, privacy guidance and troubleshooting.
- `scripts/Collect-WindowsMetrics.ps1`: root-process identity check to prevent vacuous pass after exit/PID reuse.

## Evidence collected in this environment
- Full pytest suite: 100 passed.
- Python compilation: PASS.
- JavaScript syntax: PASS for app/orb/orb-renderer.
- Metatron product audit: 9/9 PASS.
- Live backend benchmark: PASS (see bundled example JSON).
- Live independent process sampled at 0.5-second intervals: seven samples, analyzer PASS.
- Automated suite overall: PASS_PORTABLE_ONLY.

## Important limits
- Windows PowerShell execution and its native GPU/commit counters could not be tested in this Linux container.
- No real NPU/Arc GPU execution, STT microphone, TTS audio or Windows WebView2 validation was performed.
- `psutil` is needed in the project's venv for portable PID sampling; Windows native collection itself does not need psutil.
- Use a read-only copy, review reports before sharing, and preserve baseline source checksum.
