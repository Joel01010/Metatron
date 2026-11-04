# v0.2 validation checkpoint

Validated in the build container; Windows/NPU measurements remain required on Joel's laptop.

## Automated tests

Current suite: **25 passing tests**.

Coverage includes:

- Memory priority and refusal
- LRU/priority eviction
- real unload callback on eviction (accounting cannot silently detach from runtime)
- exclusive STT implementation replacement
- idle unloading
- measured-RSS reconciliation
- memory-profile switch retains eviction hooks
- deterministic English cleanup routing
- exact S1-mini prompt/control contract + dynamic output budget
- scheduler missed-interval collapse
- Kanban assignment/moves
- execution leases
- lazy JSONL worker start/request/full unload
- bounded generic JSON-RPC event/server-request routing
- OpenCode async HTTP submission and abort
- Claude Code bounded headless command construction
- E.O.P./Ezra shared HTTP job adapter, Bearer auth, status/cancel/stats
- process-tree RSS includes child allocations
- core startup/status

## Smoke behavior

- Strict hard limit: 2816 MiB
- Managed usable budget after fixed targets + headroom: 2368 MiB
- Ternary Bonsai 9B plan: refused because the 3200 MiB reservation exceeds the managed budget
- Parakeet reservation: admitted
- Core status RSS in the Linux build container: **96.9 MiB**; `/usr/bin/time` peak RSS: **99,236 KiB (~96.9 MiB)**

The build-container RSS number is not a Windows prediction. It is evidence that control-plane features have not introduced heavyweight ML/UI imports.

## Current strict-mode target

Parakeet + S1-mini + dashboard + one lightweight local coding agent can fit logically under the 2816 MiB ceiling using provisional reservations. E.O.P. is a separate local orchestration-service reservation and does not consume the coding-agent concurrency slot. The broker uses process-tree RSS and real unload hooks when measurements become available.

External processes Metatron did not launch cannot be guaranteed by its internal broker yet; they require host-level telemetry to be included in an enforceable whole-system cap.
