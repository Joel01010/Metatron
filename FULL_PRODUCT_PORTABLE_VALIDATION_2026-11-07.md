# Metatron v1.4 — Full Product Portable Validation

Date: 2026-11-07

## Result

Portable validation is PASS for the full-product candidate. This is not a substitute for the mandatory Windows release-closure run because this environment cannot execute the Tauri/MSVC host, PowerShell qualification harness, Intel NPU/GPU checks, WebView2 desktop measurements, microphone, or the 60-minute Windows soak.

## Passed here

- 148 pytest tests collected; all passed with warnings treated as errors.
- Product/security audit: 9/9 PASS.
- Dashboard privileged allowlist remains 35 commands.
- 12 product workspaces present.
- Python compileall PASS.
- JavaScript syntax PASS for `ui/app.js`, `ui/orb.js`, and `ui/orb-renderer.js`.
- Single canonical orb renderer preserved.
- Portable control-plane benchmark: 0.8693 ms command p95; provisional bridge gate is 15 ms.
- Backend process-tree working set during the portable benchmark: ~98.35 MiB.

## Product-completion regression scope

Coverage includes Orb/Pet/Both Presence modes, Solar/Lattice/Reactor core geometry, four validated companions, legacy pet migration, Reduced Motion, companion-only WebGL fallback, click-through Presence, hidden deterministic startup, system tray recovery, schedule lifecycle, approvals, explicit agent execution and run reconciliation, and unchanged authorization boundaries.

## Mandatory final Windows run

From the extracted candidate root, the normal operator path is simply:

```text
Double-click TEST-METATRON.cmd
```

No Python path, model path, Windows ML runtime, speech command, TTS command, Rust toolchain, or Visual Studio workload needs to be selected by the operator. The launcher prepares/repairs the test machine, then provisions/repairs speech and Kokoro prerequisites, runs portable + Rust + PowerShell + build + hardware + speech/TTS + EZSTT + Presence/desktop gates, performs the default 60-minute soak, captures the Presence mode matrix, writes an SBOM, and creates a zipped evidence bundle on PASS or FAIL.

Authenticode remains credential-dependent; use `-RequireSigned` only when a valid publisher certificate/private key is available.
