# Runtime capability contract

The core protocol is versioned. `protocol.info` reports protocol version, features, certified-core surfaces and experimental surfaces.

Optional speech-sidecar commands:

- `ping`
- `list_ov_devices`
- `set_device`
- `set_mode`
- `set_injection`
- `set_cleanup`
- `set_hotkey`
- `set_app_policy` — optional active-app privacy enforcement
- `set_personalization` — optional dictionary/context synchronization

Optional sidecar events:

- `level`
- `state`
- `placement`
- `transcript`
- `active_app`

Unsupported optional capabilities must degrade visibly to local-policy/local-dictionary mode without breaking core dictation.
