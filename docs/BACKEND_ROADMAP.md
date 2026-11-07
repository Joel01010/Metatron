# Metatron backend roadmap — v1.4 final implementation state

## Release-closure implementation complete

The v1.4 candidate now contains the product/runtime work that previously sat between the professional UI and a clean Windows qualification:

- SQLite WAL state, event journal, Kanban/task/scheduler state and bounded maintenance.
- Normalized E.O.P./Hermes, Ezra, Codex, Claude Code and OpenCode adapters with explicit capability/status surfaces.
- 2816 MiB strict managed-memory admission ceiling with real eviction hooks, process-tree accounting, Job Object ownership/peak commit and system-pressure policy.
- Versioned JSONL control plane and the existing 35-command dashboard authorization boundary.
- Pinned EZSTT single-process integration, Parakeet provisioning, truthful OpenVINO placement proof, active-app privacy enforcement, dictionary/context synchronization, transcript/history controls, focus/restart/E2E qualification.
- Kokoro premium TTS provisioning plus Windows SAPI fallback/interruption qualification.
- Deterministic bottom-right Presence placement against the primary monitor work area.
- Windows NPU/GPU/CPU proof, microphone capture, desktop memory/CPU, USER/GDI/handle/thread leak telemetry and 60-minute soak orchestration.
- Spectral theme system, Theme Studio, reduced motion, and Home widget visibility/reordering without widening the privileged command surface.

## Deliberately external / credential-dependent release step

Authenticode signing cannot be completed in source without the publisher certificate/private key. `Sign-Windows.ps1`, `Verify-WindowsArtifacts.ps1 -RequireSigned`, and `Invoke-MetatronReleaseClosure.ps1 -RequireSigned` provide the publication gate once a real certificate is supplied.

## Future enhancements (not v1.4 release blockers)

- richer execution leases/artifact streaming/retry semantics for external coding agents;
- optional placement-specific memory-reservation tuning from a larger fleet of certified traces;
- optional OpenVINO idle device-memory release if wake latency is acceptable;
- release-to-release statistical regression comparison;
- additional enterprise credential/update channels.

These are future product enhancements, not missing integration required for the final v1.4 qualification run.
