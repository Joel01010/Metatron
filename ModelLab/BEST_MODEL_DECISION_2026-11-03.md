# Best Speech-to-Text Model Decision — 2026-11-03

Target machine:
- Windows 11
- Intel Core Ultra 7 155H
- Intel AI Boost NPU
- memory-efficient unified JARVIS/EZSTT platform

## Final recommendation

### Default production model on the 155H NPU
**Parakeet Unified 0.6B**

Keep it as the production default today.

Why:
- purpose-built for English dictation + streaming
- punctuation/capitalization
- already supported by EZSTT
- already exported for OpenVINO
- already known to compile on Intel NPU
- one model serves push-to-talk and streaming
- no second STT stack needed

### Experimental NPU upgrade candidate
**Orukeet INT8 ONNX**

Test this first.

Orukeet is a September 2026 derivative of Parakeet TDT 0.6B v3. It keeps the same fundamental inference operators and ships a verified INT8 ONNX archive using the standard Parakeet TDT layout.

Published Orukeet vs stock Parakeet-v3:
- LibriSpeech test-clean: 1.46% vs 1.53% WER
- LibriSpeech test-other: 2.86% vs 3.14%
- FLEURS English: 3.82% vs 4.28%
- pooled FLEURS 25 languages: 9.85% vs 11.01%
- improves 61 / 74 tested splits

Important caveat:
- final adaptation/checkpoint selection used LibriSpeech test-other, so do not treat those LibriSpeech numbers as an untouched holdout.
- there is not yet a published Intel Core Ultra 155H NPU Orukeet benchmark.

Why it is still worth trying:
- official INT8 ONNX export
- standard Parakeet v3 encoder/decoder/joiner layout
- fitted Gabor filters are materialized as ordinary convolution weights
- OpenVINO NPU can compile ONNX graphs directly
- this is much more realistic to port to the NPU than a large autoregressive speech LLM

Promotion rule:
**Do not replace Parakeet Unified until Orukeet passes the NPU compile + real microphone benchmark on this laptop.**

### High-quality local mode, not NPU
**Qwen3-ASR 1.7B on Intel iGPU**

Use as an optional QUALITY profile.

Why:
- substantially stronger ASR accuracy than old Whisper/Parakeet-v3 on public benchmarks
- robust multilingual + accent support
- supports 30 languages + 22 Chinese dialects
- OpenVINO 2026.4 officially supports Qwen3-ASR on CPU/GPU

Why not default:
- OpenVINO 2026.4 does not list Qwen3-ASR as NPU-supported
- larger memory footprint
- slower than Parakeet in community real-world use
- the 155H iGPU shares system memory

Use it only after unloading the NPU STT model if memory pressure matters.

### Multilingual NPU fallback
**Whisper Large v3 Turbo INT8**

Use when:
- you need language coverage beyond Parakeet/Orukeet
- Qwen3-ASR iGPU memory/latency is unacceptable
- you specifically want NPU execution

## Absolute best open-weight STT model overall

As of 2026-11-03, ignoring laptop constraints:
**NVIDIA Nemotron 3.5 Transcribe 30B-A4B**

It was released 2026-10-28 and reports:
- 4.71% mean WER on 9 public English Open-ASR sets
- 4.62% multilingual Open-ASR mean
- speaker-attributed transcription
- style control
- word timestamps
- long-form transcription

Do NOT try to run this on the Core Ultra 7 155H NPU.

Official serving profiles target H100 / RTX PRO 6000-class GPUs and the model has a 30B MoE backbone with roughly 4B active parameters.

## Newer Parakeet-family models

### Parakeet Ultra
Very strong September 2026 post-training of Parakeet v3:
- Open ASR 7-set English average: 5.80 vs 6.26 for stock v3
- FLEURS 25-language average: 9.55 vs 11.62
- business speech: 5.79 vs 6.15
- background noise: 5.82 vs 6.72
- long-form TED-LIUM: 1.94 vs 2.71

It may be the strongest 0.6B Parakeet-family checkpoint in broad published benchmarks.

Why it is not the NPU default:
- published runtime is Photon on NVIDIA GPU
- no first-party Intel OpenVINO NPU export was found
- Orukeet already ships an ONNX INT8 artifact that is more practical to test on Intel NPU

### Orukeet
Not clearly superior to Ultra on every aggregate benchmark, but currently the **best NPU-port candidate** among the newer Parakeet descendants.

## Production policy

Use this order:

```text
LEAN / English / production:
    Parakeet Unified 0.6B -> Intel NPU

EXPERIMENTAL NPU QUALITY:
    Orukeet INT8 -> Intel NPU
    promote only after local benchmark win

QUALITY:
    Qwen3-ASR 1.7B -> Intel iGPU
    unload NPU STT model first if memory constrained

MULTILINGUAL NPU:
    Whisper Large v3 Turbo INT8 -> Intel NPU

ABSOLUTE BENCHMARK CHAMPION:
    Nemotron 3.5 Transcribe -> not suitable for this laptop
```

## Local benchmark is the final authority

For dictation, benchmark the user's real voice:
- Indian English
- technical vocabulary
- VIT/course/project names
- code identifiers
- casual speech
- background fan/room noise
- 5–30 second utterances

A model that scores better on LibriSpeech but loses names, punctuation, code terms, or latency is not the better dictation model.
