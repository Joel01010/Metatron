# Contributing

Contributions are welcome. Keep the project memory-first and local-first.

## Requirements for changes

- Do not add an always-resident runtime when a disposable worker is sufficient.
- Do not report an accelerator as active until the underlying runtime confirms placement.
- Preserve NPU → GPU → CPU fallback unless a user explicitly changes the policy.
- Keep high-rate visualization/audio events out of persistent SQLite event storage.
- New agent integrations must support bounded logs/output and clean cancellation.
- New settings must have safe defaults and must not store secrets in ordinary SQLite settings.
- Add tests for backend behavior.

Run before opening a PR:

```powershell
python -m pytest tests
python -m compileall -q metatron scripts
node --check ui/app.js
node --check ui/orb-renderer.js
```
