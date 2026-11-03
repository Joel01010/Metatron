# Memory Optimization Plan

These are design targets, not guaranteed measurements. The local agent must measure the real machine after building.

## Profiles

### LEAN — recommended default

Loaded:
- Tauri shell
- one small overlay WebView
- EZSTT Python/OpenVINO sidecar
- one STT model
- microphone stream

Not loaded:
- assistant panel
- LLM client history beyond zero
- wake-word model
- computer-use
- screenshot capture
- TTS until needed

Recommended model:
- Parakeet Unified 0.6B for English
- Whisper Small English if you want the lightest Whisper option

### BALANCED

Loaded:
- everything in LEAN
- assistant panel on demand
- bounded assistant history
- HTTP client to a local/remote LLM
- Windows speech synthesis only while speaking

Not loaded:
- embedded LLM
- computer-use unless invoked
- wake model by default

### FULL

Loaded on demand:
- assistant panel
- tool system
- optional computer-use
- optional wake-word engine

Even in FULL:
- keep one STT model
- do not embed a second Whisper stack
- do not run Electron
- do not keep screenshots in history except the latest one or two
- do not duplicate the local LLM if Ollama/llama.cpp already owns it

## Specific implementation rules

### UI

- Vanilla TypeScript for overlay.
- No React for the 24/7 overlay.
- CSS/SVG, no Three.js.
- `requestAnimationFrame` only during active voice visualization.
- pause ring animations while hidden.
- no `setInterval(16ms)` loops.
- no DOM re-render per audio sample.
- update transforms/styles directly.

### STT

- one transcriber object
- one model mapped at a time
- unload and GC before switching very large models
- keep OpenVINO cache
- do not load Parakeet and Whisper simultaneously
- do not keep CPU fallback model loaded alongside NPU model

### Assistant

- bounded deque/history
- text only by default
- max 12 messages in memory in LEAN/BALANCED
- cap ordinary replies to ~384 tokens
- stream output if later implemented, but do not accumulate duplicate copies of the same transcript
- summarize/trim old history instead of letting it grow forever

### Images / computer-use

OpenDex correctly noticed that old screenshots dominate context.

For a memory-first port:
- keep newest screenshot only by default
- never retain raw screenshot bytes in UI state after the tool result has been consumed
- save temporary screenshots to disk if an audit trail is needed
- delete them after the task unless user requests retention

### Audio

- keep one microphone stream open if that prevents clipping
- do not record WAV unless streaming archive is explicitly enabled
- release long session audio buffers incrementally
- do not duplicate raw audio in both UI and Python

### TTS

Default:
- WebView/Windows `speechSynthesis`

Avoid:
- loading a neural TTS model into the same process by default

### Wake word

OFF by default.

Continuous wake-word models are a permanent memory/CPU cost for a feature the user may not need.

## Measurement commands

PowerShell:

```powershell
Get-Process | Where-Object {
  $_.ProcessName -match 'ezstt|engine|msedgewebview2|python'
} | Select-Object ProcessName,Id,
  @{N='WorkingSetMB';E={[math]::Round($_.WorkingSet64/1MB,1)}},
  @{N='PrivateMB';E={[math]::Round($_.PrivateMemorySize64/1MB,1)}}
```

Measure:
1. app idle before model load
2. model loaded / idle
3. listening
4. transcribing
5. assistant panel open
6. local LLM server separately

Report the delta, not just total system RAM.
