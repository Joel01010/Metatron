# Metatron v1.4 — Final Implementation Handoff

Date: 2026-11-06  
Candidate intent: one final target-Windows qualification pass, not another cloud/local implementation loop.

## 1. What is closed in this candidate

### UI / product
- Spectral UI and Theme Studio remain intact across all 12 workspaces.
- Home secondary widgets can be shown/hidden and reordered from Settings; Presence remains fixed.
- Reduced-motion, density, typography and Presence controls persist through validated settings.
- The Rust dashboard authorization surface remains exactly 35 commands; no new privileged UI bridge was added.

### Speech / EZSTT
- Pinned EZSTT revision: `5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a`.
- `Setup-SpeechRuntime.ps1` is idempotent: clone/fetch/pin, venv/dependencies, Metatron adapter, command manifest, environment wiring, Parakeet model provisioning and optional verification.
- `Provision-EZSTTModel.py` drives EZSTT's own protocol to install/select/verify `parakeet-unified-en-0.6b` on NPU (or CPU when explicitly selected).
- `ezstt_metatron_sidecar.py` is a single-process compatibility adapter; it imports the pinned engine rather than keeping a duplicate resident STT model.
- Placement is trusted only when OpenVINO `EXECUTION_DEVICES` confirms the requested device class.
- Foreground-app events, per-app `allow` / `no_context` / `pause`, context profile propagation and dictionary personalization are runtime-active.
- Privacy pause is checked before capture and again before injection. Paused text is not written to history and is not learned by the dictionary.
- First protocol line remains EZSTT `hello`; foreground monitoring cannot race ahead of it.
- `Invoke-EZSTTQualification.ps1` auto-builds the pinned debug Tauri shell when missing and runs protocol → focus → restart → E2E.

### TTS
- Kokoro fp16 provisioning is idempotent and exports configuration into the current qualification process as well as the user environment.
- Final release closure requires the Kokoro benchmark.
- Windows SAPI interruption remains the fallback and its test uses real asynchronous cancellation rather than accepting full-clip playback as a PASS.

### Presence / desktop
- Floating Presence is deterministically anchored 24 physical pixels from the bottom-right of the **primary monitor work area**, so taskbar space is respected.
- Resize re-anchors the window.
- The native orb probe launches/cleans up the app and verifies visibility, bounds and the deterministic anchor.

### Memory / reliability
- Strict managed-memory admission ceiling remains **2816 MiB**.
- Windows process-tree accounting prefers private commit and rejects partial coverage.
- Owned workers expose Job Object peak process/job commit evidence.
- System pressure reacts to low available RAM or high system commit (90% strict/voice; 92% agent) by evicting recomputable workers and reducing Presence to Eco.
- Long-soak metrics include private working set/bytes, system commit, CPU, handles, threads, churn and USER/GDI object counts.
- GPU performance-counter collection is timeout-bounded and unavailable counters stay `null`; direct OpenVINO compile+infer remains the accelerator placement authority.

### Windows automation hardening
- The historical PowerShell `$args` collision, malformed spacing, stale pytest temp, resource/icon packaging, parser, native-stderr, GPU-counter-hang and orb-position regressions are locked down by source/tests or the final orchestration.
- Native Git/npm/pip/Python invocations in provisioning/qualification temporarily use `ErrorActionPreference=Continue` and then enforce the real process exit code, avoiding Windows PowerShell 5.1 stderr-as-terminating-error false failures.
- Full Metatron validation runs in a child PowerShell process so its exit code cannot suppress the independent EZSTT qualification evidence.
- The final closure always writes a machine-readable summary, SBOM and a sibling zipped evidence bundle on PASS or FAIL.

## 2. Portable validation completed before packaging

- `148 tests collected` in the current self-testing candidate.
- All 148 tests passed under `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `-W error`, split into two equivalent partitions because the combined suite exceeded the sandbox's single-command execution timeout.
- `python -m compileall -q metatron scripts tests`: PASS.
- `node --check ui/app.js`, `ui/orb.js`, `ui/orb-renderer.js`: PASS.
- Product/security audit: **9/9 PASS**.
- Dashboard backend commands: **35 implemented / 35 authorized**.
- One canonical orb renderer: PASS.
- Portable bridge benchmark p95 on this sandbox: approximately **0.8693 ms** vs 15 ms gate.

Rust/MSVC, PowerShell parsing and physical NPU/GPU/microphone/WebView2 qualification cannot run in the Linux packaging environment. They are intentionally included in the one target-Windows command below.

## 3. Prior Windows evidence used as regression baseline

The supplied qualification reports establish that the reference Windows/Core Ultra machine has already demonstrated:

- real OpenVINO NPU/GPU/CPU compile+infer;
- real microphone capture;
- corrected SAPI interruption in tens of milliseconds rather than waiting for a ~44 s clip;
- passing desktop build/packaging after canonical fixes;
- low idle shell memory/CPU;
- a passing 60-minute soak with only a small positive Private Bytes slope;
- the only historical GPU-counter problem was counter-provider availability/hanging, not lack of direct OpenVINO GPU proof.

This candidate preserves those proven core limits and re-runs them because the UI/speech/telemetry tree changed.

## 4. Current self-testing Windows entry point

**This section supersedes the older hand-entered PowerShell procedure for the current package.** From the candidate root, double-click:

```text
TEST-METATRON.cmd
```

The launcher prepares/repairs the local test environment itself and then:

1. provisions/repairs pinned EZSTT;
2. provisions/selects/verifies Parakeet Unified 0.6B;
3. installs the Metatron EZSTT compatibility adapter;
4. verifies Metatron↔EZSTT placement;
5. provisions Kokoro fp16;
6. prepares OpenVINO/audio qualification dependencies;
7. runs portable tests/audit/benchmarks and PowerShell parsing;
8. runs Rust fmt/check and the Windows desktop build;
9. proves NPU/GPU/CPU and microphone behavior;
10. verifies Presence placement;
11. runs SAPI and Kokoro tests;
12. runs idle desktop metrics and the 60-minute soak;
13. builds/runs EZSTT protocol/focus/restart/E2E;
14. generates an SBOM and final JSON summary;
15. creates one sibling evidence ZIP whether the result is PASS or FAIL.

The first run may download the Parakeet model, Kokoro fp16 model/voices, Python packages and npm/Rust dependencies if not already cached.

## 5. Only credential-dependent publication step

Authenticode signing cannot be completed without the publisher certificate/private key. Source support and verification gates are present. When the real signing credential is available, sign the artifacts and re-run artifact verification, or add `-RequireSigned` to the final closure command.

A missing Windows GPU performance-counter provider is not treated as a false zero or fake PASS. OpenVINO compile+infer proof is the hardware placement gate; perf counters remain supplementary telemetry.
