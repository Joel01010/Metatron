# Windows memory metric definitions

Metatron deliberately reports several memory metrics because no single Windows process counter captures a WebView2 + iGPU/NPU + disposable-worker application accurately.

- **Working set**: physical pages currently resident for a process/process tree. It includes shared pages and can shrink when Windows trims memory. It is useful for instantaneous RAM residency, not as the sole admission-control metric.
- **Private working set**: resident, non-shareable pages. The Windows qualification collector requires complete process-tree coverage before publishing this total.
- **Private commit / Private Bytes**: `PROCESS_MEMORY_COUNTERS_EX.PrivateUsage` / Process `PrivateMemorySize64`. This is committed private virtual memory and can remain charged even when pages are not resident. Metatron prefers complete process-tree private commit when learning a worker's memory charge.
- **System commit used / limit / percent**: derived from `GlobalMemoryStatusEx`. It detects whole-system commit pressure that process working sets can hide.
- **GPU shared/dedicated memory**: sampled separately on Windows because integrated-GPU allocations may not be attributable correctly by summing ordinary process working sets. Missing GPU counters are reported as unavailable, never as zero.
- **Handles / threads / process churn**: captured during soak runs because slow growth can reveal resource leaks before RAM growth becomes obvious.
- **Sampling overhead**: each sample records elapsed/overrun time so a diagnostics run that cannot keep up is not silently treated as trustworthy.

## Completeness rule

A process-tree total is published only when every process in the snapshot could be measured. Partial coverage is reported as unavailable instead of producing a deceptively small number. PID churn is recorded so short-lived children are visible in the evidence.

## Release evidence

Release qualification should publish together:

1. process-tree working set;
2. process-tree private working set;
3. process-tree private commit / Private Bytes;
4. system available physical memory;
5. system commit used, limit, and percentage;
6. GPU shared/dedicated memory and engine use when counters are available;
7. handle/thread counts and process churn;
8. first/last-quartile drift and MiB/hour slope from a warmed soak test.

Logical reservations are admission estimates, not measured RAM. A metric that is unavailable must remain unavailable rather than being substituted with `0`.
