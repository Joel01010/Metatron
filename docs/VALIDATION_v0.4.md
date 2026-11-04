# Validation — v0.4

## Automated

```text
python -W error -m unittest discover -s tests -v
36 / 36 PASS
python -m compileall -q metatron scripts tests
PASS
node --check renderer/orb/orb-renderer.js
PASS (when Node is available)
```

Cold control-plane smoke in the build environment:

```text
Metatron version: 0.4.0
Peak RSS: ~97 MiB
```

This is not a Windows 11 measurement. The 155H laptop remains the authority for final memory budgets.

## Strict-mode planning smoke

With a configured Kokoro FP16 model:

```text
Parakeet + dashboard + S1-mini + balanced orb/fixed budget: 2498 MiB reserved
Request Kokoro FP16: allowed
Victim selected: S1-mini
Projected managed load after switch: 1820 MiB before fixed/headroom accounting
```

The important property is the eviction order: STT and the visual presence survive; semantic cleanup yields to speech output.

## Renderer validation boundary

The WebGL2 source passes JavaScript syntax checks. The container has no working EGL/X display, so the shader could not be visually GPU-validated here. Run `scripts/Start-Orb-Demo.ps1` on Windows to validate the actual Intel Arc/WebView2 rendering path.
