# Metatron TTS v0.4

## Voice goal

Original male premium AI voice: composed, low-to-mid pitch, crisp, restrained and warm. It should evoke a polished sci-fi butler archetype without cloning a specific actor or character voice.

Default Kokoro voice: `am_fenrir`.

## Provider order

Premium mode:

1. Kokoro-82M ONNX lazy worker
2. Piper CLI, if configured
3. Windows male SAPI fallback

Light mode:

1. Piper
2. Windows SAPI

Off mode synthesizes nothing and unloads TTS runtimes.

## Preferred Kokoro precision

`Setup-Kokoro-TTS.ps1` now defaults to **FP16**. The upstream model-files-v1.1 release publishes FP32, FP16 and INT8 exports; FP16 is the preferred quality/memory compromise for Metatron. INT8 can be requested with `-Precision int8` when memory is more important than fidelity.

Example:

```powershell
.\scripts\Setup-Kokoro-TTS.ps1 -Root 'Z:\Metatron' -Precision fp16
```

## Echo guard / barge-in

TTS emits microphone-focus state through `AudioFocusController`:

```text
tts starts -> speech.capture.suspended
playback ends -> short acoustic tail -> speech.capture.resumed
```

Default tail: 280 ms.

If the host explicitly detects the user speaking over Metatron, call:

```text
tts.barge_in
```

This stops playback and immediately restores capture.

Environment controls:

```text
METATRON_TTS_ECHO_GUARD=1
METATRON_TTS_BARGE_IN=1
METATRON_TTS_CAPTURE_TAIL_MS=280
```

## Memory isolation

Kokoro and ONNX Runtime live in a separate Python venv/process. The worker is admitted through `ModelBroker`, measured by full process-tree RSS, and killed on idle/eviction. Metatron core never imports NumPy, ONNX Runtime, SoundFile or Kokoro.

The broker uses the configured filename to improve its initial reservation:

```text
*.int8.onnx -> ~260 MiB provisional runtime charge
*.fp16.onnx -> ~330 MiB provisional runtime charge
FP32/unknown -> ~420 MiB provisional runtime charge
```

Measured process-tree RSS replaces these estimates with a safety cushion.

## Benchmark

After setup:

```powershell
python scripts\benchmark_tts.py
```

It reports cold/warm synthesis latency, audio duration, real-time factor and worker process-tree RSS.

## Orb synchronization

TTS outputs PCM WAV. Metatron computes a compact ~30 Hz RMS envelope and emits ephemeral `tts.level` / `presence.level` events. The procedural orb consumes this envelope so AI speech radiates from the gold core outward.
