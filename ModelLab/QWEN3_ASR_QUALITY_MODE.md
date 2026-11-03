# Qwen3-ASR Quality Mode

Qwen3-ASR 1.7B is the recommended optional high-quality local mode for this platform.

## Why

Public Qwen model-card result:
- mean WER: 5.59
- LibriSpeech test-clean: 1.24
- supports multilingual recognition and automatic language identification
- 30 languages + 22 Chinese dialects

Community reports in late 2026 include users switching from Parakeet-v3 to Qwen3-ASR 1.7B because it was somewhat more accurate on real meetings with mixed accents, at the cost of lower speed.

## Hardware

OpenVINO 2026.4 explicitly lists Qwen3-ASR support on:
- CPU
- GPU

It does **not** list Qwen3-ASR under NPU-supported models.

Therefore on the Core Ultra 7 155H:

```text
Qwen3-ASR 1.7B -> Intel Arc iGPU
```

not NPU.

## Memory policy

Quality mode must:
1. unload the active Parakeet/Whisper transcriber
2. release/GC its mapped model
3. load Qwen3-ASR on GPU
4. use it only while Quality mode is selected
5. unload it when returning to NPU/Lean mode

Never keep both large speech models resident just for instant switching.

## Smaller alternative

Qwen3-ASR 0.6B:
- lighter
- official mean WER 6.31 on the June 2026 HF evaluation
- still multilingual
- better fit if 1.7B creates too much shared-memory pressure
