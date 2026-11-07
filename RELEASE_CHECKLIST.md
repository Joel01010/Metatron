# Release checklist — final v1.4 candidate

The normal release path on the target Windows machine requires no command construction:

```text
Double-click TEST-METATRON.cmd
```

The PowerShell equivalent is `scripts\Run-MetatronTests.ps1 -Mode Full`. The harness prepares the developer/test toolchain and all qualification runtimes itself.

It prepares missing Python/Git/Node/Rust/MSVC/WebView2 prerequisites when possible, creates the isolated test venv, provisions Windows ML plus an automatic ONNX probe, provisions/repairs the pinned EZSTT runtime and Parakeet model, provisions Kokoro, creates the qualification runtime, and runs portable/Rust/security/build/hardware/orb/TTS/STT/EZSTT gates, performs the 60-minute soak, generates an SBOM, and writes a single zipped evidence bundle whether the result is PASS or FAIL.

## Automated gates

- [ ] warnings-as-errors pytest suite PASS
- [ ] product/security audit 9/9 PASS; dashboard allowlist remains 35 commands
- [ ] full-product regressions PASS: core styles, four-pet validation, reduced-motion/fallback contract, automation lifecycle and tray/hidden-startup contract
- [ ] Python/JS/Tauri syntax gates PASS
- [ ] `cargo fmt -- --check` and `cargo check` PASS
- [ ] full Tauri Windows bundle builds and artifact verification PASS
- [ ] real OpenVINO NPU/GPU/CPU compile+infer proof PASS
- [ ] Windows ML application placement proof PASS
- [ ] real microphone capture PASS
- [ ] Metatron↔EZSTT placement/config/privacy/personalization PASS
- [ ] pinned EZSTT protocol/focus/restart/E2E PASS
- [ ] Windows SAPI interruption PASS and required Kokoro benchmark PASS
- [ ] deterministic primary-work-area Presence visibility/bounds PASS
- [ ] automated Presence matrix PASS with `presence-solar.png`, `presence-lattice.png`, `presence-reactor.png`, `presence-pets.png` and `presence-both.png` captured from isolated test profiles
- [ ] idle desktop memory/CPU gates PASS
- [ ] 60-minute soak/leak gate PASS with process/commit/handle/thread/USER/GDI evidence
- [ ] SBOM and machine-readable final summary generated
- [ ] evidence directory compressed to one sibling `.zip`

## Publication-only credential gate

- [ ] Authenticode-sign release artifacts and run `Verify-WindowsArtifacts.ps1 -RequireSigned`, or run the closure command with `-RequireSigned`, before public distribution/auto-update.

A missing GPU performance-counter provider is not a release failure by itself. Counter evidence remains `null` and bounded by timeout; direct OpenVINO compile+infer proof is the authoritative accelerator gate.
