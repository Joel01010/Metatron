# Release checklist

- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -W error -m pytest -q`
- [ ] `python scripts/product_audit.py`
- [ ] JS syntax and Tauri JSON checks clean
- [ ] Windows CI `cargo check` clean
- [ ] Windows preflight clean
- [ ] Real accelerator proof collected for claimed hardware
- [ ] Speech placement and latency measured
- [ ] Idle shell memory/CPU and orb GPU gates evaluated
- [ ] Job Object orphan-kill test clean
- [ ] DPAPI secret round trip clean
- [ ] UIPI/elevated-target injection behavior verified
- [ ] TTS playback/echo-guard/hotkey barge-in verified
- [ ] Model/runtime licenses reviewed
- [ ] SBOM/provenance regenerated
- [ ] Signed installer/update provenance checked before enabling auto-update

## v1.4 hardware qualification gates

- [ ] `Test-PowerShellScripts.ps1` PASS on target Windows.
- [ ] `cargo fmt -- --check` and `cargo check` PASS.
- [ ] Full Tauri Windows bundle builds and `Verify-WindowsArtifacts.ps1` PASS.
- [ ] Orb native-window visibility/bounds gate PASS.
- [ ] Direct OpenVINO NPU, GPU and CPU compile+infer gates PASS on reference hardware.
- [ ] Application model placement proof PASS through Windows ML worker.
- [ ] Real microphone capture PASS; pinned EZSTT upstream protocol/e2e/focus/restart tests PASS.
- [ ] Windows SAPI playback interruption PASS; premium TTS benchmark PASS when release assets are configured.
- [ ] Idle/certified-core memory gates PASS with complete process coverage and commit measurements.
- [ ] 30-minute minimum soak/leak gate PASS (longer pre-release soak recommended).
- [ ] Release artifacts are signed and `signtool verify /pa` PASS before publication.
