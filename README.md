# Metatron

Metatron is an open-source, Windows-first **AI operations console** designed to keep local AI useful on machines with limited RAM while still taking advantage of modern NPUs and GPUs.

It combines:

- NPU-first local inference with GPU and CPU fallback
- a procedural pale-red / golden reactive AI presence
- local TTS for important system replies
- agent control for E.O.P./Hermes, Ezra, Codex, Claude Code and OpenCode
- Kanban task orchestration and approvals
- scheduling, telemetry and memory governance
- customizable appearance, presence, voice, hardware, privacy and agent policies
- a framework-free Tauri dashboard to keep runtime memory low

## Hardware policy

The default accelerator policy is:

**all routable NPUs → all routable GPUs → CPU**

Metatron does not assume that a requested device is the device actually used. A runtime must report successful placement before the dashboard marks a workload as active on NPU/GPU/CPU.

### NPU support

The Windows ML path is vendor-neutral. Metatron accepts any execution-provider device that Windows ML reports as hardware type `NPU`; known compatible families include:

- Intel NPU via OpenVINO
- Qualcomm Hexagon NPU via QNN
- AMD Ryzen AI NPU via VitisAI
- future NPU EPs exposed through Windows ML device enumeration

GPU fallback supports the execution providers available to the local Windows ML/ONNX Runtime installation. Direct OpenVINO discovery is also supported for Intel systems.

The lightweight core does **not** bundle every vendor runtime. Use `scripts/Setup-WindowsML.ps1` to create an isolated Windows ML runtime, then use the Hardware page to inspect or ensure compatible execution providers.

## Memory goal

The default `strict` profile uses a **2816 MiB hard logical ceiling** for Metatron-managed components. Large workers are lazy and evictable.

Typical policy:

- backend/control plane: ~100–180 MiB target
- procedural orb: 90 / 180 / 280 MiB reservation (Eco/Balanced/Spectacle)
- dashboard WebView: ~260 MiB reservation while open
- one STT model resident
- S1-mini cleanup only when needed
- premium TTS only while speaking
- one local coding agent in Strict mode
- remote Ezra work does not consume a local agent slot
- 9B local assistants are refused in Strict mode

These are admission reservations, not fabricated measurements. Metatron replaces estimates with measured process-tree RSS when it owns the process.

## Presence

The floating orb and dashboard orb share a single semantic state model:

- user speech: energy flows **inward**
- thinking: core condenses and filaments accelerate
- Metatron speech: golden energy propagates **outward**
- success / warning / approval / error: transient signal pulses

The renderer is procedural WebGL2: no video loop, no texture pack, no 3D engine, no React runtime.

## Voice

TTS defaults to **important system replies only**.

Provider order:

1. Kokoro-82M ONNX (premium; isolated worker)
2. Piper (lightweight fallback)
3. Windows SAPI male voice (zero-download fallback)

TTS is optional and can be disabled. Echo guard suppresses microphone capture while Metatron is speaking, and barge-in can stop TTS immediately.

## Agents

Built-in adapters:

- **E.O.P. / Hermes Local** — existing E.O.P. FastAPI API
- **Ezra / Hermes Cloud** — same API contract remotely
- **Codex** — app-server JSON-RPC
- **Claude Code** — transient headless jobs
- **OpenCode** — headless HTTP sessions

Metatron exposes explicit Start/Stop/Submit controls. Scheduled actions are visible and persist in SQLite.

## Development

### Backend only

```powershell
python -m pip install -e ".[dev]"
python -m pytest tests
python -m metatron.main
```

The backend uses JSONL on stdin/stdout. Example request:

```json
{"id":1,"cmd":"status","params":{}}
```

### Windows ML accelerator runtime

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\scripts\Setup-WindowsML.ps1
python .\scripts\Verify-WindowsML.py
```

The setup uses Microsoft's framework-dependent Windows ML Python packages, keeping the Metatron core small.

### Desktop development

Prerequisites:

- Windows 11 recommended
- Python 3.11–3.13
- Rust stable MSVC
- MSVC C++ Build Tools
- WebView2
- Tauri CLI 2.x

Run:

```powershell
.\scripts\Start-Dev.ps1
```

### Build installer

```powershell
.\scripts\Build-Windows.ps1
```

This packages the Python control plane as a sidecar and builds the Tauri application.

## Settings

The app currently exposes persistent settings for:

- Appearance: pale-red accent, gold, density, reduced motion
- Presence: quality, desktop/dashboard orb, always-on-top, scale, bloom
- Voice: TTS toggle, premium/light mode, voice, speed, speech priority
- Hardware: accelerator order, CPU fallback, adaptive visuals
- Memory: Strict / Voice / Agent profile
- Privacy: local telemetry, transcript/audio persistence, cloud-context default
- Agents: launch confirmations, Kanban behavior, local concurrency

Settings are stored locally in Metatron's SQLite database.

## Privacy

Metatron is local-first. The control plane does not upload telemetry. Remote/cloud agents are separate explicit transports. API keys are expected through environment variables or OS-secure storage in future integrations; they are not written into the task/event database.

## Model weights and third-party assets

This repository does **not** bundle model weights, proprietary execution providers, copyrighted character art, or third-party agent binaries. Setup tools and adapters connect to user-installed runtimes.

The pet subsystem accepts user-provided skins through the future `private-assets`/skin path; copyrighted Flins/Genshin art is intentionally not included in the public repository.

## Repository structure

```text
metatron/          dependency-light Python control plane
ui/                framework-free Tauri WebView UI
renderer/orb/      procedural presence renderer reference
src-tauri/         native desktop host / Python sidecar bridge
scripts/           setup, build and benchmark helpers
tests/             backend unit and protocol tests
docs/              architecture, NPU, memory and integration docs
```

## License

Metatron source code is released under the MIT License. Third-party models, execution providers, agent CLIs, and user-supplied skins keep their own licenses.
