# Model Lab

This folder tests newer STT models without destabilizing the production dictation stack.

## Current policy

Production:
- Parakeet Unified 0.6B on Intel NPU

Experimental NPU challenger:
- Orukeet INT8 ONNX

Quality mode:
- Qwen3-ASR 1.7B on Intel iGPU via OpenVINO

Multilingual NPU:
- Whisper Large v3 Turbo INT8

## Why Orukeet gets the NPU experiment slot

Orukeet:
- is only ~0.6B
- is derived from Parakeet-v3
- ships INT8 ONNX
- uses the standard Parakeet TDT encoder / decoder / joiner layout
- stores its special Gabor kernels as ordinary convolution weights

That makes it realistic to compile the heavy encoder to Intel NPU while keeping the tiny decoder/joiner on CPU, which is the same general split used by high-performance Parakeet OpenVINO implementations.

## Run

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\Install-Orukeet-NPU-Lab.ps1
```

Then:

```powershell
.\.venv-orukeet\Scripts\python.exe .\probe_orukeet_npu.py `
  --model-dir .\orukeet-model
```

The probe does **not** claim transcription success. It tests the critical first gate: whether the official Orukeet ONNX encoder can be parsed and fully compiled by OpenVINO for `NPU` without silently falling back.

If it fails because of dynamic shapes, the local coding agent should adapt the static-window shaping logic from the existing Parakeet-v3 OpenVINO/eddy path.

## Promotion gate

Orukeet becomes the production default only if all pass:

1. full encoder compiles on NPU
2. no CPU fallback for the encoder
3. three real microphone dictations succeed
4. accuracy >= Parakeet Unified for the user's voice
5. release-to-text latency is acceptable
6. no DEVICE_LOST instability
7. memory usage is not materially worse
