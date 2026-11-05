# Source provenance

Metatron v1.2.0 was developed from the user handoff archive:

- archive: `Metatron_OpenSource_v1.1.1_Fixed.zip`
- SHA-256: `ae6777ca03d387dbd999ea3ff6de018ffc7b9e33224326d2e991efde50cae07f`
- baseline Git commit: `6d9c92612dc038518e64dc587f4ab44b1fa243b3`

The second commit applies the amended P0-P6 hardening work. The Git bundle shipped beside the source archive preserves both commits.

## v1.4.0 qualification hardening

v1.4.0 is derived from the re-audited v1.3.0 source package in this handoff. It adds hardware-qualification gates and diagnostics hardening without importing third-party branding or model weights. The OpenVINO, Tauri, Windows signing, python-sounddevice and EZSTT integrations use their documented public APIs or invoke an installed upstream test suite; no third-party source tree is vendored into Metatron by these changes.
