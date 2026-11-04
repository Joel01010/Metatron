# Agent integration strategy

Metatron uses the lightest stable programmatic surface available for each agent. Interactive TUIs are not kept open merely to make an agent manageable.

## Codex — implemented

Current integration: `codex app-server --listen stdio://`.

Metatron initializes the app-server over newline-delimited JSON-RPC, creates a thread with `thread/start`, begins work with `turn/start`, stores only bounded recent events, and surfaces server-initiated approval requests separately. `turn/interrupt` is exposed for cancellation.

This is preferable to screen-scraping the Codex terminal because app-server is designed for embedded applications, persistent threads, streamed events and approvals.

References:
- https://developers.openai.com/blog/codex-as-a-platform
- https://github.com/openai/codex/tree/main/codex-rs/app-server

## OpenCode — implemented

Current integration: `opencode serve --hostname 127.0.0.1 --port 4096`.

Metatron can use an already-running server or start one on demand. Task submission creates a session and uses `/session/:id/prompt_async`, so the Metatron control loop never waits for the model turn. Session abort is supported.

If `OPENCODE_SERVER_PASSWORD` is set, Metatron sends HTTP Basic authentication using the documented username/password mechanism.

Reference:
- https://opencode.ai/docs/server/

## Claude Code — implemented

Claude Code is deliberately transient rather than a resident daemon:

```text
claude -p "..." --output-format json --max-turns N
```

Metatron writes stdout/stderr to bounded files, returns immediately after launch, exposes the final JSON result, caps `--max-turns`, and supports `--resume`, model selection and permission mode. Its memory reservation is released when the process exits.

Reference:
- https://docs.anthropic.com/en/docs/claude-code/cli-usage

## E.O.P. / Hermes Local — implemented through its existing API

The connected E.O.P. repository already exposes a FastAPI control surface, so Metatron does **not** import E.O.P.'s FastAPI/LiteLLM/Qdrant/Redis/Langfuse stack into its own process.

Metatron uses:

- `GET /health` — availability
- `POST /jobs` — asynchronous task submission
- `GET /jobs/{id}` — job status/progress/result
- `GET /jobs` — bounded job listing
- `POST /jobs/{id}/cancel` — cancellation
- `GET /stats` — E.O.P. subsystem statistics

Protected endpoints use E.O.P.'s existing Bearer-token mechanism. Set the key only in the environment; Metatron never persists it to SQLite.

Configuration:

- `METATRON_EOP_URL` (default `http://127.0.0.1:9200`)
- `METATRON_EOP_API_KEY` (falls back to `EZEROS_API_KEY` in the current process)
- `METATRON_EOP_WORKSPACE`
- `METATRON_EOP_START_COMMAND` — optional; only when set may Metatron start/stop a local E.O.P. process itself

If E.O.P. was started externally, Metatron will never kill that external process when you press Stop; it only terminates a process it launched itself.

## Ezra / Hermes Cloud — implemented through the same E.O.P. API

Ezra uses the same HTTP job contract as E.O.P. local, so the future UI can treat local/cloud Hermes uniformly. It never consumes a local coding-agent slot.

Configuration:

- `METATRON_EZRA_URL` — preferred full base URL
- `METATRON_EZRA_HOST` — convenience host; if URL is unset Metatron derives `http://<host>:9200`
- `METATRON_EZRA_API_KEY`

A NetBird hostname/IP can be used in the URL/host without adding a separate always-on SSH subprocess.

## Memory rule for agents

The strict profile permits **one local coding runtime** (`codex`, `claude-code`, or `opencode`) at a time. E.O.P. is classified as a local orchestration service instead, so Hermes can remain connected while one coding agent works beneath it. Ezra is remote.

Provisional reservations:

- E.O.P. local service: 384 MiB when charged
- Codex app-server: 180 MiB
- Claude Code: 220 MiB while executing
- OpenCode headless server: 240 MiB

Metatron now measures the **whole descendant process tree**, not only the parent PID, and replaces provisional coding-agent estimates with measured RSS. Memory eviction is wired to real `stop()` callbacks, so an evicted managed agent is actually terminated rather than merely disappearing from accounting.

External processes that Metatron did not start cannot be forcibly reclaimed by the broker. Their RAM is outside the enforceable Metatron-managed ceiling and must be monitored separately until E.O.P. exposes host/process telemetry.
