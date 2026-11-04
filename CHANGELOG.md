# Changelog

## 1.1.0

- Made NPU-first routing a fixed invariant: every routable NPU is attempted before any GPU.
- Added GPU fallback across every routable GPU before optional CPU fallback.
- Separated hardware detection from runtime routability so Device Manager entries cannot be falsely selected.
- Windows ML provider setup now prepares all catalog providers by default, allowing future certified NPU EPs without a Metatron source update.
- Legacy OpenVINO EP routing now pins `device_type=NPU`, then `GPU`, then `CPU` instead of inferring NPU from provider name.
- Hardware dashboard now distinguishes routable vs detected-only accelerators.
- Added regression tests for multi-NPU ordering, GPU fallback, and fixed policy enforcement.


## v0.4.0 — Procedural Presence + Runtime Pressure Control

- Added a dependency-free **WebGL2 procedural Metatron orb** with pale-red spectral shell and golden volumetric core.
- Inward user-speech and outward AI-speech animation semantics implemented in the renderer.
- Adaptive Eco/Balanced/Spectacle resolution and FPS; no video/GIF/Three.js dependency.
- Added renderer cold-start packet (`presence.renderer_state`).
- Added `AudioFocusController` with TTS echo suppression, acoustic tail and explicit barge-in.
- Added `tts.barge_in` and `audio_focus.status` protocol commands.
- Added OS-level memory-pressure response: unload recomputable workers and degrade orb to Eco.
- Memory broker made thread-safe for concurrent TTS/maintenance/UI/agent activity.
- Kokoro setup now defaults to FP16 model-files-v1.1 and supports INT8/FP32 selection.
- Added TTS benchmark harness with latency, real-time factor and process-tree RSS.
- Kokoro provisional reservation now adapts to FP16/INT8 filename before real RSS is learned.
- Added standalone orb demo launcher.
- 36 tests passing.

## v0.3.0 — Voice Presence

- Reactive presence/orb state machine.
- Important-system-only local TTS policy.
- Kokoro/Piper/SAPI provider stack.
- Audio envelope events for orb synchronization.
- TTS settings persistence and memory-aware provider admission.