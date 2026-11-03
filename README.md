# Unified NPU JARVIS Platform

This is a merge kit for combining:

- **EZSTT** — `aurickk/EZSTT`
- **OpenDex / JARVIS** — `aviarytech/jarvis`

into **one Windows/Tauri application** optimized for low memory use on an Intel Core Ultra 7 155H.

Pinned upstream revisions used by this kit:

- EZSTT: `5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a`
- OpenDex: `0cc8c643e82661295b674d3de90daa8e5524e27b`

## The key design choice

Do **not** run both upstream apps side-by-side.

That would keep:
- Electron
- React
- OpenDex STT/WASM/Vosk
- EZSTT Python/OpenVINO STT
- two microphone pipelines
- duplicate UI runtimes

alive at the same time.

Instead, the unified platform uses:

```text
                ┌───────────────────────────────┐
Microphone ───► │ EZSTT Python sidecar          │
                │ OpenVINO + Intel NPU          │
                │ Parakeet / Whisper            │
                └─────────────┬─────────────────┘
                              │ JSON-line protocol
                              ▼
                ┌───────────────────────────────┐
                │ ONE Tauri/WebView2 shell      │
                │                               │
                │ JARVIS Lite HUD               │
                │ Dictation overlay             │
                │ Optional assistant panel      │
                │ Optional TTS                  │
                └───────────────────────────────┘
```

OpenDex contributes its **visual language, assistant flow, bounded conversation ideas, and tool architecture**. EZSTT remains the authoritative audio/STT runtime.

## Memory-first rules

1. One desktop shell: **Tauri/WebView2**, never Electron + Tauri.
2. One microphone capture path: EZSTT.
3. One STT model loaded at a time.
4. No Transformers.js Whisper, no Vosk STT, and no local Whisper WASM in the UI.
5. No React runtime for the overlay.
6. JARVIS reactor is SVG/CSS + a tiny `requestAnimationFrame` loop only while active.
7. Full assistant panel is created only when requested.
8. Wake word is OFF by default.
9. Conversation history is bounded.
10. Computer-use/screen capture is opt-in and loaded only on demand.
11. A local LLM is accessed through an already-running Ollama/llama.cpp/OpenAI-compatible endpoint rather than embedded inside the app process.
12. TTS uses Windows/WebView speech synthesis by default instead of a resident TTS model.

## What is implemented in this kit

The `patch_payload` folder contains a **drop-in JARVIS Lite overlay** written in vanilla TypeScript/CSS. It plugs directly into EZSTT's existing `engine-event` protocol and therefore uses:

- real `LISTENING`
- real `TRANSCRIBING`
- real `INJECTED`
- real `ERROR`
- real microphone `level` data
- real selected model/device metadata

No React or Electron is required.

It also contains a small `agent_bridge.py` that provides an optional bounded-history assistant client for an OpenAI-compatible HTTP endpoint. It is deliberately dependency-free so enabling assistant mode does not add another Node runtime.

## Local build workflow

Run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\Bootstrap-Unified.ps1
```

That:
- clones both repositories
- checks out the pinned revisions
- creates a merge branch
- copies this kit into the EZSTT checkout
- applies the JARVIS Lite overlay
- leaves OpenDex as a read-only source/reference tree

Then give your local coding agent:

`AGENT_MERGE_PROMPT.md`

## Why this is more memory efficient

OpenDex upstream is Electron + React and includes optional local STT/wake stacks. EZSTT upstream is already a very small Tauri shell around the NPU sidecar.

The merged architecture therefore takes the **features** from OpenDex without retaining its heavyweight duplicate runtime.

See `MEMORY_PLAN.md` for the target operating profiles.


## November 3, 2026 model update

The current model policy is now:

- Production Intel-NPU default: **Parakeet Unified 0.6B**
- Experimental Intel-NPU challenger: **Orukeet INT8**
- Optional higher-accuracy local quality mode: **Qwen3-ASR 1.7B on Intel iGPU**
- Multilingual NPU fallback: **Whisper Large v3 Turbo INT8**
- Overall open-weight accuracy leader: **Nemotron 3.5 Transcribe**, but it is not suitable for this laptop

See `ModelLab/BEST_MODEL_DECISION_2026-11-03.md`.

The local agent is instructed to try Orukeet on the NPU and promote it only after a real benchmark win. This avoids replacing a proven model merely because a newer model has attractive vendor benchmark numbers.
