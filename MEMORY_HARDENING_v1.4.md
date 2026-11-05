# Metatron v1.4 — memory hardening and next optimization targets

## Implemented in this corrected source

- Complete-tree private commit is preferred for learned worker charges on Windows; complete-tree working set is only the fallback.
- Partial process-tree measurements are rejected rather than undercounted.
- The Windows collector records private working set, working set, Private Bytes, system available memory, system commit/limit/percent, GPU shared/dedicated memory when available, CPU, handles, threads, process churn and sampling overhead.
- The soak analyzer validates sample completeness and observation duration before evaluating leak slope.
- The soak reports peak memory, first/last quartile drift, MiB/hour growth, handle/thread drift and churn.
- A requested soak runs even when an unrelated release gate fails.
- Diagnostic GPU polling is rate-limited so the observer is less likely to distort the workload.
- TTS and coding-agent learned reservations use the safer process-tree charge metric.

## Highest-value next optimizations after the next Windows run

### 1. Add Job Object peak-commit evidence
Windows Job Objects already own Metatron workers. Query `JOBOBJECT_EXTENDED_LIMIT_INFORMATION.PeakJobMemoryUsed` and `PeakProcessMemoryUsed` for each owned worker. This gives an OS-maintained peak-commit signal that survives short spikes between periodic samples. Use it as extra telemetry, not as a replacement for the process-tree collector.

### 2. Tune reservations from measured placement-specific p95
The current NPU/GPU/CPU reservations are intentionally conservative. After 5–10 repeated qualification runs, calculate p95 private commit for Parakeet on each placement and reduce reservations only where the evidence is stable. Keep the existing 10% cushion.

### 3. Expose an idle memory-release command in OpenVINO workers
OpenVINO 2026 exposes `CompiledModel::release_memory()` and NPU graph eviction support. If the speech/cleanup worker owns a compatible compiled model, add a sidecar command that releases device memory after an idle interval while keeping the process alive. Benchmark wake-up latency before enabling it by default.

### 4. Add system-commit pressure policy
The application already records system commit. After baseline measurements, add a conservative high-commit trigger (for example, a configurable percentage) alongside the existing minimum-available-RAM trigger. Do not hard-code a threshold until the reference machine has repeatable idle/STT/TTS/agent traces.

### 5. Add USER/GDI-object leak counters
WebView/window leaks may first appear as growing USER/GDI object counts rather than large Python RAM growth. Add `GetGuiResources` counts for the Tauri/WebView2 processes to long soaks.

### 6. Add scenario-separated memory budgets
Store baselines separately for idle shell, dashboard, orb Eco/Balanced/Spectacle, STT NPU/GPU/CPU, TTS loaded/speaking/idle-unloaded, and each agent. A single whole-app threshold can hide a regression in one scenario.

### 7. Add release-to-release baseline comparison
Keep the machine-readable JSON from every certified build. Fail CI/qualification on statistically meaningful regressions in idle private working set, private commit, startup commit delta, or leak slope even when absolute limits still pass.

## Recommended order

1. Run the corrected 30–60 minute soak and collect the full evidence bundle.
2. If growth is flat, run scenario-specific captures for STT/TTS/orb/agents.
3. Tune reservation estimates from p95 private commit.
4. Add Job Object peak memory and USER/GDI counters.
5. Only then consider more aggressive OpenVINO memory release, because it trades memory for warm-resume latency.
