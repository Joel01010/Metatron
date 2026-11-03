# Validation Checklist

## Build

- [ ] EZSTT pinned base checkout succeeds
- [ ] `npm run build` succeeds after JARVIS Lite payload
- [ ] Tauri build succeeds
- [ ] installer launches on Windows 11

## NPU

- [ ] `NPU` appears in `openvino.Core().available_devices`
- [ ] selected STT model compiles on NPU
- [ ] no silent CPU fallback
- [ ] model switch releases prior model

## Dictation

- [ ] hold hotkey
- [ ] toggle mode
- [ ] text injection
- [ ] clipboard restore
- [ ] no focus stealing
- [ ] silence rejection
- [ ] streaming mode

## JARVIS UI

- [ ] reactor appears immediately on listening
- [ ] real microphone amplitude moves core
- [ ] no rAF loop while hidden/idle
- [ ] transcribing state visible
- [ ] injected state gives success pulse
- [ ] errors readable
- [ ] model/device label correct
- [ ] overlay watchdog still receives pong

## Memory

Measure process memory for:
- original EZSTT
- unified LEAN
- unified LEAN while listening
- unified BALANCED with assistant panel
- EZSTT + OpenDex running separately

The important comparison is unified vs both upstream apps running together.

## Assistant

- [ ] disabled by default
- [ ] no extra LLM model memory when disabled
- [ ] local endpoint connection only on use
- [ ] bounded history
- [ ] API key absent from logs
