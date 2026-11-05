# Metatron diagnostics & performance qualification — v1.4.0

This toolkit is **read-only**, does not require administrator privilege for ordinary process sampling, installs nothing, sends nothing to the network, and does not read dictation history or SQLite databases. Run from a **copy** of the source. Use the project's virtual environment (never the system Python for package installs). `psutil` is required for the portable process sampler; Windows native performance sampling works without it.

## Quick start on reference Windows laptop

Open PowerShell in the Metatron source directory:

```powershell
$Py = 'D:\path-to-your-venv\Scripts\python.exe' # Replace with your actual venv path
& $Py -c "import psutil; print(psutil.__version__)" # Must succeed for process sampling
& .\scripts\Invoke-MetatronDiagnostics.ps1 -Python $Py -Bundle
```

This runs bounded Python tests, compilation, UI JS checks, product audit, and control-plane benchmark, collecting local logs and a redacted summary bundle. It **does not** install engines, build an installer, start/stop Metatron, edit state, or prove NPU placement.

For memory telemetry, start Metatron independently (prefer your normal desktop launcher), then identify **its actual process ID** in Task Manager > Details. Do not guess the PID. This records a 2-minute observation:

```powershell
& .\scripts\Invoke-MetatronDiagnostics.ps1 -Python $Py -ProcessId 12345 -Seconds 120 -Bundle
```

If Windows GPU counters time out or fail, the native collector marks them **null** and includes an error; for CPU/memory-only capture:

```powershell
& .\scripts\Invoke-MetatronDiagnostics.ps1 -Python $Py -ProcessId 12345 -Seconds 120 -SkipGpu -Bundle
```

The `-SkipGpu` result is **not a GPU qualification PASS**. The GPU engine/VRAM columns remain unknown. Check counter provider/driver availability separately, not by silently accepting zero utilization.

Opt into limited application-crash event summaries with `-IncludeEventSummaries` (timestamps, provider and event ID only; no sensitive event messages).

## Individual collectors

```powershell
& $Py scripts/diagnostics/process_sampler.py --pid 12345 --seconds 300 --interval 1 --out build/diagnostics-process.jsonl
& $Py scripts/diagnostics/analyze_telemetry.py build/diagnostics-process.jsonl --out build/diagnostics-analysis.json
& .\scripts\Collect-WindowsMetrics.ps1 -RootProcessId 12345 -DurationSeconds 300 -OutFile build/metrics-windows.json
& $Py scripts/diagnostics/analyze_telemetry.py build/metrics-windows.json --out build/metrics-windows-analysis.json
& $Py scripts/diagnostics/analyze_telemetry.py build/metrics-windows.json --baseline build/baseline-windows.json --out build/metrics-comparison.json
```

The Windows PowerShell collector has native **working set, private working set, private bytes/commit, system commit, available memory**, GPU shared/dedicated usage and 3D engine %, subject to counter availability. It can be slower than one-second intervals: inspect `max_sample_gap_s` for lost temporal resolution. The portable sampler records RSS, USS, CPU seconds, thread and handle counts (where supported), I/O byte counters, process counts and system availability. **USS ≠ Windows private commit.** A sum of process RSS can double-count shared pages. GPU shared memory should not be added blindly to process private bytes.

## Repeatable experiment matrix

Use identical build, power mode, resolution, display topology and warm-up for each run; retain baseline JSON reports and exact version/hash.

| Scenario | Warm-up | Measure | What to observe |
|---|---:|---:|---|
| Cold launch | none | 60 s | Time to first usable UI, peak commit, child process births |
| Idle desktop + orb hidden | 30 s | 180 s | Private WS p95, CPU median/p95, handles/threads |
| Orb eco vs balanced | 20 s each | 120 s | GPU engine, frame smoothness, resource delta |
| Dictation warm | 30 s | 180 s | Actual provider, model worker commit, latency p95 |
| NPU unavailable → GPU | until warmed | 120 s | Verified session placement, fallback time, memory |
| NPU/GPU unavailable → CPU | until warmed | 120 s | CPU fallback only if policy allows |
| TTS + interruption | 20 s | 120 s | Audio focus, voice worker memory, barge-in latency |
| Agent start/stop cycle | 30 s | 300 s | Orphans, handles, retained memory, timeout behavior |
| Long idle/soak | 1 min | 1800+ s | Baseline and final private commit, resource growth |

Do not use synthetic placement claims to certify accelerator behavior. Real on-device STT microphone/latency and WebView2 visual checks remain manual or require device-specific instrumentation.

## Report interpretation

- `CAPTURED_NOT_CERTIFIED`: enough telemetry exists for diagnosis; it does not establish a product release gate.
- `INCOMPLETE`: missing samples, root died, or PID reused; rerun and investigate.
- A null `private_commit_mib` or `gpu_3d_percent` means **unavailable**, not zero.
- `process_count` changing unexpectedly may indicate workers that launch/exit; correlate with application logs, but note the 1-second sampler may miss very short-lived processes.
- Compare two same-scenario reports using `--baseline`; p95 deltas are descriptive, **not** statistically significant from one run.
- For memory leak hypotheses, look at private commit growth over long stable-idle windows, handle/thread growth and child process churn; repeat runs and isolate model cache from leaks.

## Privacy and handoff

The diagnostic runner emits per-command stdout/stderr to the local output directory. **Inspect these before sharing**, as Python test output or runtime errors can include personal filesystem paths. `-Bundle` on the Windows entrypoint excludes raw logs and raw process timelines by default; review the JSON summaries and inventory before sharing too. Do not include transcripts, microphone recordings, tokens, `.env`, DPAPI secrets, databases, browser profiles, or raw crash dumps. Keep the original outputs locally for investigation.

## What cannot be vetted in Linux

Windows PowerShell syntax/behavior, GPU PDH counter availability, job ownership, desktop WebView2 behavior, Intel NPU execution and physical audio are device-gated. This package may include tests for command-line contracts, but they are **not** a substitute for hardware observation.

## Windows-specific troubleshooting

When GPU counters are missing, test them in an isolated terminal with a **short bounded collection**; avoid blindly looping `Get-Counter` for minutes. Run `Get-Counter -ListSet 'GPU Engine'` and `'GPU Process Memory'` and inspect whether the sets exist. A counter set may be absent, its provider may be unhealthy, or the driver may expose alternate instances. Do not treat a missing set as a GPU with 0% activity. If a metrics run hangs, rerun `-SkipGpu` to collect CPU and memory evidence while resolving GPU provider problems.

When private working set or system commit readings are absent, treat memory certification as incomplete. If cold-start numbers fluctuate, capture clean before-and-after system snapshots, repeat runs, and cross-check the app's own memory reservations against measured process private commit. For high GPU shared-memory use, inspect the **dedicated/shared GPU counters separately**, since integrated GPUs borrow system RAM.

For crashes, the opt-in event summaries show provider/ID/time only. Keep detailed Windows Error Reporting records on the target computer and inspect them locally; do **not** automatically publish raw dumps or event messages, which can expose memory and paths.

## Versions and provenance

This is a diagnostic addition to the corrected v1.4.0 release candidate. Tests inside this package are an engineering smoke gate, **not** certification of Windows-native PowerShell, GPU counters or actual speech inference. The provided ZIP is a *source package*; no unsigned Windows executable is included.
