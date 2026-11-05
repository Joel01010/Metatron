# Metatron diagnostics re-audit — 2026-11-05

## Verdict
Portable code checks PASS. **No claim of zero pending work is justified.** The Windows native collector has not been executed on Windows and product hardware qualification is outstanding.

## Corrections made in this re-audit
1. Windows process-tree memory and CPU aggregates now become `null` unless *every discovered PID* was successfully measured. This prevents partial sums and missing private working-set performance data from masquerading as measured zeros.
2. Diagnostic runner's shareable summary no longer reproduces arbitrary subprocess arguments (which may contain Windows user directories or project paths).
3. Two regression tests were added to protect these contracts.

## Reproduced in the Linux environment
- Test suite: **102 pytest tests passed**; `unittest discover`: **46 tests passed**.
- Product/security audit: **9/9 pass**.
- Python compilation and UI JavaScript syntax checks: **pass**.
- Automated runner's test/compile/audit/Node suite: **PASS_PORTABLE_ONLY**.
- Automated runner's backend benchmark: **PASS_PORTABLE_ONLY**.
- Both original uploaded archive ZIPs: integrity verified before patching.
- Re-audit package's ZIP integrity and clean extraction: verify before deploying.

## Still pending / hardware gated
- Execute Windows PowerShell diagnostics collector and test GPU-counter availability, timeout/cancel behavior, private working-set and committed-bytes values against independent tools.
- Build/run native Tauri/Rust on Windows (including WebView2, orb z-order and multi-monitor positioning, MSI/NSIS).
- Install and validate actual EZSTT/Parakeet and Kokoro/Piper assets and microphone/speaker integration.
- Prove Intel NPU actual execution, Intel Arc GPU fallback, CPU-last fallback and latency.
- Measure complete process-tree memory, system commit, GPU engine and shared/dedicated GPU memory across cold/warm/soak scenarios and compare against full qualification thresholds.
- Independently verify signing, license/model provenance and actual installer on target platform.

Do not submit this as a finished Windows certification. Keep Linux benchmarks distinct from target-machine data. No local device changes or external agent transmissions occurred.
