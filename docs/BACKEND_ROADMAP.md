# Metatron backend roadmap

## Phase B0 — complete in this prototype

- SQLite WAL state store
- event journal + in-process event bus
- Kanban CRUD/status transitions
- approval queue
- interval scheduler persistence
- normalized agent registry
- E.O.P. local Hermes and Ezra cloud Hermes profiles
- Codex / Claude Code / OpenCode capability adapters
- telemetry persistence + process RSS sampling
- hard memory budget broker
- model catalog including Parakeet, S1-mini, and Bonsai
- JSON-lines protocol for later Tauri integration

## Phase B1 — next

1. Integrate with the existing EZSTT sidecar instead of adding a second Python resident process.
2. Wire real agent transports:
   - Codex app-server
   - Claude Code noninteractive/session interface
   - OpenCode serve
   - E.O.P. Hermes local runtime
   - Ezra Hermes over authenticated SSH/NetBird
3. Add task execution leases, cancellation, logs, artifacts, retries, and session IDs.
4. Implement Windows process-tree telemetry and child RSS tracking.
5. Add token/TTFT/tok-s adapters per agent/model.
6. Add scheduler policies and user-authorized automation rules.
7. Add secrets abstraction using Windows Credential Manager/DPAPI.
8. Add bounded event/telemetry retention jobs.

## Phase B2 — speech intelligence

- deterministic Flow parser: punctuation, lines, paragraphs, URL/email normalization, snippets, dictionary, filler removal
- S1-mini optimized local provider behind `CleanupProvider`
- benchmark NPU vs Intel Arc iGPU vs CPU
- preserve STT responsiveness: cleanup cannot block mic/control loop
- idle unload S1-mini after configurable timeout

## RAM acceptance criteria

At idle, with dashboard closed:

- backend + STT + pet/overlay target <= 2.0 GiB
- hard failure / eviction before 2.75 GiB logical managed budget
- dashboard may raise total, but whole platform still target <= 3.0 GiB
- starting any component that cannot fit must either evict an optional model or be refused with a clear reason
- 9B local assistant is disabled under strict-budget mode; cloud/CLI agents remain available
