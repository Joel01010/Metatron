# Memory policy

Metatron's default target is a 2–3 GiB whole-platform envelope.

## Strict profile

Hard logical ceiling: 2816 MiB.

The control plane owns reservations for optional components. Before loading a worker, it checks whether it fits, evicts lower-priority idle resources when safe, then reconciles estimates with measured process-tree RSS.

Protected behavior:

- STT has higher priority than cleanup/TTS/dashboard.
- The procedural orb degrades to Eco under system memory pressure instead of being destroyed.
- S1-mini is recomputable and is an early eviction candidate.
- Premium TTS is disposable.
- Cloud Ezra does not consume local model memory.
- 9B assistants are not admitted under Strict profile.

## Runtime profiles

- Strict: 2816 MiB, one local coding agent.
- Voice: 2560 MiB, dashboard expected closed, aggressive idle eviction.
- Agent: 3072 MiB, upper edge, more local agent tooling.

## Measurement

Metatron never treats an estimate as a measurement. For owned processes it samples the entire process tree because agent CLIs frequently spawn child processes.
