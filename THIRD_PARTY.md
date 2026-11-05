# Third-party components

Metatron does not redistribute the following by default. Their licenses remain separate from Metatron's MIT license.

- Windows ML / Windows App SDK / ONNX Runtime and execution providers (Microsoft and silicon vendors)
- Intel OpenVINO
- Qualcomm QNN
- AMD VitisAI / MIGraphX
- NVIDIA execution providers
- Kokoro model/runtime
- Piper voices/runtime
- S1-mini by Superwhisper
- Parakeet model weights
- E.O.P./Hermes, Codex, Claude Code and OpenCode binaries/services
- user-supplied pet/skin artwork

Review upstream license terms before redistributing any binary or model weight in a packaged fork.

## Qualification/runtime references added in v1.4

- **EZSTT** (`aurickk/EZSTT`) — MIT code; Metatron does not redistribute its protected branding/assets. The qualification wrapper runs the pinned upstream test scripts in-place when the user has installed that runtime.
- **python-sounddevice** — MIT; optional qualification dependency used to open and sample the real default microphone endpoint.
- **OpenVINO** — Apache-2.0; optional qualification runtime used for direct NPU/GPU/CPU compile-and-infer proofs.

These tools are not bundled as model weights. Review their licenses and the existing model license gate before redistribution.
