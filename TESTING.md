# Testing Metatron — no local agent knowledge required

## Normal release qualification

On the target Windows 11 machine:

1. Extract the ZIP to a normal writable folder.
2. Double-click **`TEST-METATRON.cmd`**.
3. Accept a UAC prompt if Windows needs to install Visual Studio Build Tools or another missing prerequisite.
4. When the EZSTT focus test says it is waiting for the desktop to become idle, stop using the keyboard and mouse until that test finishes.
5. Let the script complete. The full path includes a **60-minute memory soak**.

That is the complete operator procedure. You do not need to choose a Python environment, model path, NPU provider, speech command, TTS command, or build toolchain manually.

The launcher automatically:

- checks Windows 11 and WebView2;
- installs missing Python 3.12, Git, Node.js LTS, Rustup and Visual Studio 2022 C++ Build Tools through `winget` when possible;
- creates an isolated Metatron test venv and installs the test dependencies;
- selects the stable MSVC Rust toolchain;
- provisions the qualification OpenVINO/audio runtime;
- provisions Windows ML and creates a tiny local ONNX placement-probe model;
- provisions the pinned EZSTT revision and Parakeet Unified 0.6B model;
- installs Metatron's EZSTT compatibility sidecar;
- provisions Kokoro fp16 TTS;
- runs PowerShell parser/smoke checks;
- runs the complete warnings-as-errors pytest suite, Python compile checks, JS syntax checks, product/security audit and bridge benchmark;
- runs `cargo fmt --check`, `cargo check`, the Tauri Windows build and installer checks;
- proves real OpenVINO NPU/GPU/CPU compile+inference;
- exercises Windows ML with the generated ONNX probe;
- captures the real microphone endpoint;
- verifies Metatron↔EZSTT placement, privacy/personalization protocol and upstream protocol/focus/restart/E2E behavior;
- benchmarks Kokoro and verifies Windows TTS interruption;
- verifies the native Presence window and automatically captures isolated Solar, Lattice, Reactor, Pet-only and Both screenshots;
- measures desktop resource use and performs the 60-minute soak/leak gate;
- generates an SBOM and JSON summaries;
- creates one evidence ZIP whether the overall result is PASS or FAIL.

## Output

Every run creates:

```text
build\self-test-YYYYMMDD-HHMMSS\
build\self-test-YYYYMMDD-HHMMSS.zip
```

Read `SELF-TEST-SUMMARY.json` first. The matching ZIP is the file to send back for analysis if the result is FAIL.

The nested `01-release-closure\final-closure.json` is the canonical full-release verdict.

## Quick regression

Double-click **`TEST-METATRON-QUICK.cmd`** for a much shorter portable + Automation Center regression run. It is useful after code-only edits but **does not replace the full Windows qualification**.

## Targeted reruns

These are available when a specific full-run stage fails. They all accept an evidence directory and are orchestrated by `scripts\Run-MetatronTests.ps1`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Portable
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Hardware
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Speech
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode TTS
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Presence
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Automation
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Packaging
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Memory -SoakMinutes 60
```

Normally you should not need these. Run the top-level `.cmd` first and use the evidence ZIP to decide whether a targeted rerun is necessary.

## Signing

Authenticode signing cannot be created by the test harness because the publisher private key is intentionally external. After a real certificate is configured, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Run-MetatronTests.ps1 -Mode Full -RequireSigned
```

A missing signature is therefore a publication credential issue, not an implementation/test-environment issue.
