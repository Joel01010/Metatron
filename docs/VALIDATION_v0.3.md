# Validation — Metatron Backend v0.3

Validation environment: OpenAI Linux build container. These figures are not a substitute for Windows 11 / Core Ultra 7 155H measurements.

## Automated checks

- `python -m compileall -q metatron scripts tests` — PASS
- `python -W error -m unittest discover -s tests -v` — **32/32 PASS**
- JSONL protocol smoke covering status, user speech levels, orb quality, dashboard accounting, TTS status and live event ring — PASS

## Cold core footprint

`/usr/bin/time -v` on a one-request backend process:

- Maximum RSS: **99,472 KiB (~97.1 MiB)**
- Cold strict logical platform reservation: **628 MiB**
  - backend target 160 MiB
  - pet/overlay base 64 MiB
  - safety headroom 224 MiB
  - balanced orb reservation 180 MiB

## Strict-mode planning checks

- Parakeet + balanced orb + S1-mini + dashboard: admitted.
- Starting Kokoro premium TTS in that configuration: admitted by evicting **S1-mini first**.
- Dashboard and orb remain admitted during premium speech.
- 3.2 GiB Ternary-Bonsai local assistant: refused under Strict Mode.

## Still requires Windows validation

1. Real Kokoro-ONNX RSS/latency and voice quality on the laptop.
2. Real Piper/SAPI fallback behavior.
3. Windows `winsound` playback synchronization against the 30 Hz envelope.
4. Tauri/WebView + WebGPU renderer RSS for Eco/Balanced/Spectacle modes.
5. Intel NPU STT + iGPU/CPU TTS concurrent latency and power behavior.
