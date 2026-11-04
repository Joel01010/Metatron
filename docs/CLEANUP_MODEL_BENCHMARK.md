# S1-mini cleanup runtime contract

Metatron's English-only semantic cleanup candidate is **S1-mini by Superwhisper**. It is a 596M-unique-parameter text normalizer fine-tuned from Qwen3-0.6B. The official model card reports a 462 MiB quantized build and recommends dictation-length inputs under roughly 1,000 tokens.

Official model: https://huggingface.co/superwhisper/s1-mini

## Exact input contract

Do not invent a generic cleanup prompt. S1-mini was trained on an exact system prompt plus a control line. `metatron.cleanup.S1MiniConfig.messages()` owns that format.

Required defaults:

- Styling: `semi-formal`
- Structure: `prose`
- Context: `general`
- greedy decoding / temperature 0
- Qwen3 thinking disabled
- output budget: approximately `1.3 * input_tokens + 32`, capped at 1024
- empty output is valid for filler-only input

## Why the model stays out of Metatron core

OpenVINO/Transformers/llama.cpp runtime libraries are never imported into the control plane. The chosen runtime is a disposable JSONL worker admitted through `ModelBroker`, launched on first semantic-cleanup request, and killed after idle so the OS can reclaim its full heap/runtime allocation.

## Local benchmark before promotion

Use `scripts/benchmark_cleanup_worker.py` with each candidate runtime/device. It checks:

- output correctness on a small English smoke set
- cold + first-request latency
- p50/p95 request latency
- **process-tree** peak RSS
- configured RAM/latency ceilings

Example protocol command once an OpenVINO worker is implemented:

```powershell
python scripts/benchmark_cleanup_worker.py --max-rss-mib 650 --max-p95-ms 750 -- `
  python scripts/s1_openvino_worker.py --device GPU
```

Benchmark GPU, NPU and CPU. Do not promote an NPU path merely because compilation succeeds: Parakeet/Orukeet already need the NPU, so whole-system voice latency under concurrent STT matters more than isolated cleanup TPS.
