# Architecture

```text
Tauri / WebView2
  |-- Dashboard (plain HTML/CSS/JS)
  |-- Floating procedural orb
  |
  +-- JSONL bridge
        |
        +-- Metatron control plane (~dependency-free Python)
              |-- Settings / SQLite WAL
              |-- Event bus
              |-- Kanban / runs / approvals / schedules
              |-- Memory governor
              |-- Hardware manager
              |-- Presence state machine
              |-- TTS manager
              |-- Agent registry
              |
              +-- disposable workers / external services
                    |-- Windows ML / OpenVINO inference
                    |-- STT
                    |-- S1-mini cleanup
                    |-- Kokoro TTS
                    |-- Codex / Claude Code / OpenCode
                    |-- E.O.P. local
                    +-- Ezra remote
```

## Design rules

1. Core stays small and dependency-light.
2. Heavy ML libraries live in child processes.
3. One local coding-agent slot in Strict mode.
4. High-rate audio/orb events are ephemeral, bounded in RAM.
5. Persistent state is SQLite; secrets are not.
6. Every hardware workload separates preferred placement from actual placement.
7. UI is replaceable without rewriting backend logic.
