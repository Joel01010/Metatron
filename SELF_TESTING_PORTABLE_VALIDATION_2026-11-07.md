# Metatron v1.4 — Self-Testing Candidate Portable Validation

Date: 2026-11-07

## Result

Portable validation is **PASS** for the self-testing candidate. This does not claim that the exact ZIP is Windows-qualified; the Windows-specific Rust/MSVC, PowerShell, WebView2, physical accelerator, microphone, focus and 60-minute soak gates must execute on the target Windows machine.

## Exact-tree portable results

- pytest: **148 / 148 PASS** with warnings treated as errors;
- Python compile checks: PASS;
- JavaScript syntax: PASS for `ui/app.js`, `ui/orb.js`, `ui/orb-renderer.js`;
- product/security audit: **9 / 9 PASS**;
- workspaces: **12**;
- dashboard privileged allowlist: **35 commands**;
- single canonical orb renderer: PASS;
- full-system self-test tooling presence audit: PASS;
- portable command p50: **0.6125 ms**;
- portable command p95: **0.8693 ms** versus the 15 ms gate;
- backend process-tree working set during benchmark: **98.35 MiB**.

## Self-testing regression scope

Regression tests now assert that the package contains the top-level launchers, automatic machine preparation, every targeted wrapper, ONNX probe generation, isolated Presence-profile generation, automatic Windows ML/speech/Kokoro preparation, prepared-interpreter use in build/support-bundle paths, and evidence packaging. The product audit fails if required full-system test tooling is missing.

## Final Windows instruction

```text
Double-click TEST-METATRON.cmd
```

No hand-selected Python, `ModelPath`, `METATRON_WINML_PYTHON`, `METATRON_SPEECH_CMD`, Kokoro path, Rust toolchain or Visual Studio workload is part of the normal operator procedure.
