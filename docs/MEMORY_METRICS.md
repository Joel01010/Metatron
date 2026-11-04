# Windows memory metric definitions

Metatron reports several metrics because no single process metric captures an iGPU/NPU workload accurately.

- **Working set**: physical pages currently resident for a process/process tree. It can include shared pages and can shrink under OS pressure.
- **Private commit**: `PROCESS_MEMORY_COUNTERS_EX.PrivateUsage`; committed private virtual memory. This is not the same as private working set.
- **System commit used**: `GlobalMemoryStatusEx(total page file - available page file)`; used to detect whole-system pressure that process accounting misses.
- **GPU shared memory**: must be captured on Windows with GPU Engine/Process Memory PDH counters during certification. It is not folded into the Python process number.

Release benchmarks must publish process-tree working set, process-tree private commit, system commit delta, available-memory delta, and GPU shared-memory counters together. Logical reservations are admission-control estimates, not measured RAM.
