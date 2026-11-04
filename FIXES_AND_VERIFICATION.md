# Metatron v1.1.1 — Verified source repair

## Findings

- The original v1.1 ZIP, when freshly extracted, passes **47/47 pytest tests** and **36/36 unittest-discover tests**. The previously reported `FlowPreprocessor` NameError does **not** reproduce in the packaged v1.1 source: `metatron.cleanup.RuleCleaner` is present and used. Do not add a fake class to work around a stale workspace.
- Fixed a real version mismatch: `pyproject.toml` advertised v1.1.0 while runtime `status()` and `metatron.__version__` returned v1.0.0. All Python and Tauri version declarations now report v1.1.1.
- Added a regression assertion that the status API reports the package version.

## Validation commands

```powershell
python -m pip install -e '.[dev]'
python -m pytest -q
python -m unittest discover -s tests -v
python -m compileall -q metatron scripts tests
node --check ui/app.js
node --check ui/orb-renderer.js
cd src-tauri; cargo check
```

Linux validation here ran pytest/unittest/compile/JS checks and JSONL smoke. Rust/Tauri and actual Windows ML NPU/GPU inference require a Windows toolchain and real hardware; they are **not certified** by these checks.

## Known unfinished capabilities, not test failures

- S1-mini runtime is an interface, not a complete optimized inference worker.
- Cross-vendor NPU device enumeration and provider selection exist, but vendor drivers, actual model compilation, and execution-provider placement must be tested on target hardware.
- The strict RAM ceiling is an admission-control budget, not a proof of real Windows whole-process-tree memory without live telemetry.
- UI/Tauri packaging and production installer require Windows build and smoke testing.
