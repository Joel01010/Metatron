# Metatron v1.4 — memory hardening status

## Implemented in the final implementation candidate

- The strict managed admission ceiling remains **2816 MiB**. No UI/runtime work in this pass raises it.
- Complete-tree private commit is preferred for learned worker charges on Windows; complete-tree working set is only the fallback.
- Partial process-tree measurements are rejected rather than undercounted.
- Windows Job Objects expose OS-maintained `PeakProcessMemoryUsed` and `PeakJobMemoryUsed` evidence for owned workers, covering short commit spikes between samples.
- The Windows collector records private working set, working set, Private Bytes, system available memory, system commit/limit/percent, GPU shared/dedicated memory when available, CPU, handles, threads, process churn, sampling overhead, and USER/GDI object counts.
- GPU performance-counter collection is isolated behind a timeout. A driver/counter stall produces `null`/unavailable evidence and disables further polling; it is never converted to zero or a placement PASS.
- Direct OpenVINO compile+infer evidence remains the hardware placement authority for NPU/GPU/CPU qualification.
- The soak analyzer validates sample completeness and observation duration before evaluating leak slope, and reports peak memory, quartile drift, MiB/hour growth, handle/thread drift, USER/GDI drift and churn.
- A requested soak runs even when another qualification gate fails, preserving diagnostic evidence.
- Diagnostic GPU polling is rate-limited so the observer is less likely to distort the workload.
- TTS and coding-agent learned reservations use the safer process-tree charge metric.
- System pressure is asserted by either low available physical memory **or** high Windows commit usage. Strict/voice profiles use a conservative 90% commit ceiling; agent mode uses 92%. Pressure evicts recomputable optional workers and degrades Presence to Eco without increasing the hard managed budget.

## Evidence baseline carried from prior Windows qualification

The earlier qualified v1.4 tree demonstrated low idle memory/CPU and a flat 60-minute soak on the reference Core Ultra system. Those figures are regression baselines, not a substitute for re-running the final changed tree. The final one-shot qualification therefore repeats the desktop and 60-minute soak gates.

## Post-release optimization ideas (not release blockers)

1. Build placement-specific p95 reservation datasets across multiple machines before reducing conservative model reservations.
2. Evaluate OpenVINO `release_memory()`/device graph eviction only if warm-resume latency remains acceptable.
3. Keep scenario-separated baselines for idle shell, dashboard, Presence quality levels, STT, TTS and each agent.
4. Add release-to-release statistical comparison once several certified evidence bundles exist.
