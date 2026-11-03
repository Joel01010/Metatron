# Assistant Integration Patch Notes

The included `agent_bridge.py` is intentionally not wired automatically because the exact server integration is easier and safer for the local agent to apply against the checked-out EZSTT source.

## Server changes

In `engine/ezstt/server.py`:

1. Construct one `AgentBridge` in `Server.__init__`.
2. Put the config at a separate path such as:
   `%APPDATA%\EZSTT\agent.json`
3. Add:
   - `_cmd_agent_status`
   - `_cmd_agent_chat`
   - `_cmd_agent_clear`
4. Run blocking `agent_chat` outside the hotkey/audio thread.
5. Never log `api_key`.
6. Do not initialize the bridge's network connection until `agent_chat`.

Suggested commands:

```json
{"id": 20, "cmd": "agent_status"}
{"id": 21, "cmd": "agent_chat", "params": {"text": "Summarize this"}}
{"id": 22, "cmd": "agent_clear"}
```

## Why OpenAI-compatible HTTP

It allows one tiny client to talk to:
- a local Ollama OpenAI-compatible server
- llama.cpp server
- compatible gateways
- compatible hosted providers

without embedding a Node AI SDK and Electron runtime.

## OpenDex features intentionally deferred

The merge should not port these until the base memory target is proven:
- continuous Vosk wake word
- local Transformers.js Whisper
- Electron updater
- Nut.js computer control
- screenshot capture loop
- ElevenLabs SDK

They are not deleted conceptually; they become optional modules in the FULL profile.
