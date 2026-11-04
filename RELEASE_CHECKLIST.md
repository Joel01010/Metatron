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
