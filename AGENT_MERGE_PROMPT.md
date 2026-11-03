# Local Coding Agent — Merge EZSTT + OpenDex into One Memory-Optimized App

## Goal

Produce one Windows app based on EZSTT's Tauri shell, with:
- Intel NPU STT
- Parakeet/Whisper model switching
- OpenDex-inspired JARVIS UI
- optional assistant panel
- optional TTS
- optional tool layer

while avoiding duplicate runtimes and minimizing memory.

Pinned source revisions:
- EZSTT: `5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a`
- OpenDex: `0cc8c643e82661295b674d3de90daa8e5524e27b`

Read:
- README.md
- ARCHITECTURE.md
- MEMORY_PLAN.md

## Phase 1 — establish clean baselines

In both repos:
- record commit SHA
- run existing tests
- build if possible
- record baseline memory

Do not change model/runtime behavior yet.

## Phase 2 — make EZSTT the only shell

The final executable must be Tauri-based.

Do not embed or launch OpenDex Electron.

OpenDex is a source/reference repository only.

## Phase 3 — apply JARVIS Lite

Run:

```powershell
.\Apply-JarvisLite.ps1 -EzsttPath .\work\EZSTT
```

Then build EZSTT.

The replacement overlay must:
- remain click-through
- never steal focus
- react to real `level` events
- use existing engine state events
- preserve streaming state
- preserve watchdog ping behavior

Do not reimplement microphone capture in the UI.

## Phase 4 — memory profile

Add a UI-only setting:
- `lean`
- `balanced`
- `full`

LEAN is default.

At minimum, the selected profile should control whether:
- assistant UI is created
- TTS is allowed
- wake-word service is allowed
- computer-use module is allowed

Do not preload disabled modules.

## Phase 5 — assistant bridge

Integrate `patch_payload/engine/ezstt/agent_bridge.py` into the existing Python protocol server.

Add commands:
- `agent_status`
- `agent_chat`
- `agent_clear`

`agent_chat` must run off the engine's hotkey/audio-critical path.

Configuration:
- stored separately from STT config
- API key must not be logged
- history is bounded
- default disabled

For local use, support an OpenAI-compatible endpoint such as an already-running Ollama/llama.cpp server.

Do not load a local LLM inside EZSTT.

## Phase 6 — optional full JARVIS assistant window

Create a Tauri window lazily, only when user opens it.

Use vanilla TS first. Only introduce a framework if there is a compelling measurable benefit.

The window should show:
- reactor
- transcript
- model/device status
- STT state
- assistant response
- tool activity

TTS default:
- browser/WebView `speechSynthesis`

## Phase 7 — tool port

Port only lightweight skills first.

Keep computer-use OFF by default.

Any sensitive action must ask permission.

## Phase 8 — test

Required:
1. OpenVINO reports NPU.
2. Parakeet/Whisper compiles and executes on NPU.
3. Three dictations into Notepad.
4. Overlay never steals focus.
5. Clipboard restoration still works.
6. Hold mode works.
7. Toggle mode works.
8. Streaming transcription works.
9. JARVIS reactor follows real mic level.
10. Overlay hides/settles correctly.
11. Assistant disabled consumes no meaningful extra resident memory.
12. Assistant enable/disable works without restarting STT.
13. Switching models does not leave two STT models resident.
14. Existing EZSTT tests remain green.

## Memory evidence

Collect process working-set/private-memory values for:
- original EZSTT
- unified LEAN
- unified BALANCED with assistant panel open

Also compare against running OpenDex + EZSTT separately.

The merged LEAN build should be materially smaller than the two upstream applications running together.

## Deliverables

- source branch
- diff
- build artifact
- test output
- memory table
- screenshots
- third-party attribution
- exact upstream commits
- list of OpenDex modules intentionally excluded for memory reasons

## Model selection update — 2026-11-03

Read `ModelLab/BEST_MODEL_DECISION_2026-11-03.md`.

New required experiment:

1. Keep Parakeet Unified 0.6B as the known-good production NPU baseline.
2. Run `ModelLab/Install-Orukeet-NPU-Lab.ps1`.
3. If Orukeet's encoder fully compiles on NPU, integrate it as a new model type.
   - encoder: NPU
   - feature extraction / tiny decoder / joiner: CPU
   - no silent fallback
4. Benchmark Orukeet against Parakeet Unified using the user's actual microphone.
5. Promote Orukeet to default ONLY if it wins accuracy/latency/reliability on the laptop.
6. Add Qwen3-ASR 1.7B as an optional Quality profile on Intel GPU, not NPU.
7. Never load Qwen3-ASR and the NPU model simultaneously when memory optimization is enabled.

Do not select Nemotron 3.5 Transcribe for this laptop even though it is the current open-weight accuracy leader; it is far too large and is not an Intel-NPU deployment target.
