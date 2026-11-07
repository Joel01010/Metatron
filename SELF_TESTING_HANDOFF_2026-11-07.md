# Metatron v1.4 — Self-Testing Handoff

Date: 2026-11-07

## Operator contract

The normal target-Windows operator is **not expected to understand Metatron, Python environments, Rust, Visual Studio workloads, OpenVINO, Windows ML, EZSTT, Kokoro, ONNX, or the qualification harness**.

After extracting the candidate on Windows 11, the normal procedure is:

```text
Double-click TEST-METATRON.cmd
```

The only expected human interaction is accepting Windows elevation/install prompts when required and leaving the keyboard/mouse idle when the EZSTT focus test explicitly asks for idle input. The full run includes a 60-minute soak.

## What the launcher prepares automatically

- checks the host and refreshes PATH after installs;
- installs/repairs Python 3.12, Git, Node.js LTS, Rustup/MSVC, Visual Studio 2022 C++ Build Tools and WebView2 through WinGet where possible;
- repairs an existing Visual Studio Build Tools instance when the C++ VCTools workload is missing;
- creates `build/test-runtime/.venv` and installs Metatron test dependencies plus ONNX;
- selects the stable `x86_64-pc-windows-msvc` Rust toolchain;
- prepares OpenVINO/audio qualification dependencies;
- prepares Windows ML and generates a tiny deterministic ONNX placement-probe model locally;
- provisions the pinned EZSTT revision, Parakeet Unified 0.6B, and the Metatron compatibility sidecar;
- provisions Kokoro fp16 and voices;
- builds the required Metatron and EZSTT Windows artifacts when missing.

## What it tests automatically

- warnings-as-errors Python regression suite, compile checks and JS syntax;
- 9/9 product/security audit and fixed 35-command dashboard authorization boundary;
- PowerShell parsing/smoke, Rust formatting/check, Tauri build and installer verification;
- real OpenVINO NPU/GPU/CPU compile+infer and Windows ML placement;
- microphone capture;
- Metatron ↔ EZSTT placement, privacy and personalization contract;
- pinned EZSTT protocol/focus/restart/end-to-end qualification;
- Kokoro and Windows SAPI interruption;
- native Presence visibility/anchor and automatic Solar/Lattice/Reactor/Pet-only/Both captures in isolated temporary Metatron profiles;
- idle desktop resource gates and 60-minute soak/leak evidence;
- SBOM and machine-readable summaries.

## Evidence on both PASS and FAIL

The top-level runner creates:

```text
build/self-test-YYYYMMDD-HHMMSS/
build/self-test-YYYYMMDD-HHMMSS.zip
```

Read `SELF-TEST-SUMMARY.json` first. On a failure, the ZIP is intended to contain enough evidence for diagnosis without asking the operator to reproduce individual commands.

## Targeted reruns

Targeted modes exist for diagnostics after the full evidence bundle has identified a failing stage: Portable, Hardware, Speech, TTS, Presence, Automation, Packaging and Memory. They are not prerequisites for the normal run. See `TESTING.md`.

## Credential boundary

Authenticode publication signing remains intentionally external because the publisher private key/certificate cannot be generated or embedded by the test harness. `-RequireSigned` is available once the real signing credential is configured.
