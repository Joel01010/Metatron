# Unified Architecture

## Base runtime

Use EZSTT as the base repository.

Reasons:
- Tauri is much lighter than retaining a separate Electron runtime.
- Its OpenVINO/NPU sidecar already solves the hardest hardware-specific part.
- It already implements hotkeys, microphone capture, model management, injection, streaming transcription, and overlay supervision.
- The engine emits clean state and amplitude events that the JARVIS UI can consume directly.

## What moves from OpenDex

### Keep / port

- JARVIS reactor visual design
- voice-reactive HUD behavior
- transcript-oriented assistant UX
- status model
- bounded conversation history
- optional provider-backed assistant
- optional TTS
- tool permission concept
- screenshot-history pruning concept if computer-use is later enabled

### Do not retain as resident runtime

- Electron
- Electron updater
- React for the compact overlay
- local Transformers.js Whisper
- Vosk local STT
- OpenDex microphone capture
- duplicate wake/STT pipeline
- ElevenLabs SDK unless explicitly enabled
- computer-use libraries unless user enables the feature

## Process model

Normal dictation mode:

```text
ezstt.exe (Tauri)
  ├─ WebView2 overlay
  └─ engine.exe / Python sidecar
       └─ OpenVINO NPU model
```

Assistant mode:

```text
ezstt.exe
  ├─ overlay WebView
  ├─ assistant WebView (created lazily)
  └─ same engine sidecar
       ├─ same STT model
       └─ outbound HTTP to configured LLM endpoint
```

No Node/Electron process is required.

## Speech pipeline

The user presses/holds the EZSTT hotkey.

```text
Mic
→ EZSTT MicSource
→ 16 kHz audio
→ Parakeet Unified / Whisper
→ OpenVINO
→ Intel NPU
→ transcript
→ paste/type injection
→ JARVIS success pulse
```

The UI never owns the microphone.

## JARVIS reactor implementation

`patch_payload/ui/src/jarvis-lite.ts`

It uses:
- inline SVG rings
- CSS rotations
- no canvas/WebGL
- real EZSTT RMS level
- asymmetric amplitude smoothing
- `requestAnimationFrame` only while listening/recording
- no permanent high-frequency timer while idle

This is intentionally simpler than OpenDex's full React theme but visually similar.

## Optional assistant

`patch_payload/engine/ezstt/agent_bridge.py`

Design:
- no dependencies beyond Python standard library
- OpenAI-compatible endpoint
- bounded text history
- short output limit
- no embedded local LLM
- can point to Ollama/llama.cpp or a remote provider gateway
- disabled until configured

Recommended local configuration for a separate local model server:

```json
{
  "enabled": true,
  "base_url": "http://127.0.0.1:11434/v1",
  "model": "your-model-name",
  "api_key": "",
  "max_history_messages": 12,
  "max_tokens": 384
}
```

The local model server owns its model memory. The desktop app does not load another LLM into its own process.

## Full HUD

The full-screen/large JARVIS view should be another Tauri window created only when opened.

Do not keep it alive while the user only wants push-to-talk dictation.

## Future tool port

Port OpenDex skills in this order:

1. clock — tiny
2. open URL/app — permission-gated
3. weather — network only
4. web search — network only
5. computer use — opt-in, lazy loaded last

Do not preload screen capture or automation libraries.

## Security boundary

Keep the EZSTT engine protocol as the only privileged bridge.

Sensitive tools should require explicit permission before action.

Never allow arbitrary shell commands from the UI.
