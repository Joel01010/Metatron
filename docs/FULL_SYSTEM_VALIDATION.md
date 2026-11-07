# Full-system validation

Portable tests cannot certify WebView2, Windows Job Objects, DPAPI, microphone/hotkey behavior, or NPU/GPU execution. Use a Windows 11 machine for release qualification.

## Normal operator path

No local agent expertise is required.

1. Extract the candidate to a writable folder.
2. Double-click **`TEST-METATRON.cmd`**.
3. Accept UAC if Windows needs to install missing build tools.
4. Leave keyboard/mouse idle when the EZSTT focus test asks for an idle desktop.
5. Let the default 60-minute soak complete.

The runner leaves both an evidence directory and a sibling ZIP under `build\self-test-*`, even if qualification fails. Read `SELF-TEST-SUMMARY.json` first.

See `TESTING.md` for the exact automated stages and targeted rerun commands.

## What the harness prepares automatically

The machine-preparation layer checks or installs, when possible:

- Python 3.12;
- Git;
- Node.js LTS + npm;
- Rustup with the stable MSVC toolchain;
- Visual Studio 2022 C++ Build Tools;
- Edge WebView2 Runtime.

It then creates an isolated Metatron test venv and installs the test dependencies. The release-closure layer provisions Windows ML, generates a local ONNX placement-probe model, provisions the pinned EZSTT/Parakeet runtime, provisions Kokoro, and creates the separate OpenVINO/audio qualification venv.

No human-provided `ModelPath`, `METATRON_WINML_PYTHON`, `METATRON_SPEECH_CMD`, Kokoro path, or test Python is required for the normal run.

## Accelerator proof

Inventory is not proof. The full gate requires direct OpenVINO compile + inference on **NPU, GPU and CPU** on the reference Intel system. Windows ML is exercised separately with the generated ONNX probe. Requested accelerator placement is never treated as verified merely because a provider appears in a catalog.

## Speech qualification

The full runner pins and provisions EZSTT, installs the Metatron compatibility sidecar, provisions Parakeet Unified 0.6B, verifies Metatron's placement/config/privacy/personalization contract, and then runs EZSTT's protocol, focus, restart and E2E tests.

The focus test intentionally needs a quiet desktop for a short period. The operator does not need to perform any action except stop using the keyboard/mouse when the test asks.

## Presence/core/companions

The full gate compiles the Rust/Tauri host, verifies the one-renderer contract through the regression suite, probes the native Presence window, checks deterministic primary-work-area anchoring and saves `presence-window.png` as supplemental visual evidence.

## Memory and leak qualification

The default release path performs the desktop resource benchmark and a **60-minute soak**. Evidence covers process-tree working set/private bytes, whole-system commit, process churn, handles, threads, USER/GDI objects, and bounded/nullable GPU performance counters. The managed admission ceiling remains **2816 MiB**.

## Support and failure evidence

The top-level runner packages the entire run directory whether the result is PASS or FAIL. The support-bundle path separately excludes secrets, the SQLite database, transcript history and audio.

## Advanced targeted reruns

Use these only after inspecting the evidence from the normal run:

```powershell
.\scripts\Run-MetatronTests.ps1 -Mode Portable
.\scripts\Run-MetatronTests.ps1 -Mode Hardware
.\scripts\Run-MetatronTests.ps1 -Mode Speech
.\scripts\Run-MetatronTests.ps1 -Mode TTS
.\scripts\Run-MetatronTests.ps1 -Mode Presence
.\scripts\Run-MetatronTests.ps1 -Mode Automation
.\scripts\Run-MetatronTests.ps1 -Mode Packaging
.\scripts\Run-MetatronTests.ps1 -Mode Memory -SoakMinutes 60
```

Authenticode remains a publication credential gate. Add `-RequireSigned` only when a real publisher certificate/private key is configured.
