# Runtime capability contract

The core protocol is versioned. `protocol.info` reports protocol version, features, certified-core surfaces and experimental surfaces.

## Speech sidecar contract

The pinned Metatron EZSTT compatibility adapter is a **single-process** entrypoint around EZSTT revision `5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a`. It does not keep a second resident STT model. It preserves EZSTT protocol-1 ordering (`hello` is always first) and adds Metatron-owned compatibility commands/events.

Supported control surfaces include:

- `ping`
- `list_ov_devices`
- `set_config` / device, mode, injection and hotkey updates
- `set_app_policy` — foreground-app pause/no-context/context-profile enforcement
- `set_personalization` — dictionary/context synchronization
- clean `shutdown`

Supported events include:

- `level`
- `state`
- `placement`
- `transcript`
- `active_app`

Placement is marked verified only when the compiled Parakeet encoder reports the requested device class through OpenVINO `EXECUTION_DEVICES`. The pinned EZSTT revision currently supports NPU and CPU speech placement; Metatron does **not** advertise GPU speech placement merely because the machine has an OpenVINO GPU plugin.

Unsupported optional capabilities from another sidecar must degrade visibly to local-policy/local-dictionary mode without breaking core dictation. A sidecar returning `supported=true, applied=false` is treated as deferred/stale policy, not as a successful enforcement claim.
