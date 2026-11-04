# Metatron Orb Renderer v0.4

Dependency-free WebGL2 procedural renderer for the pale-red / golden-core Metatron presence.

## Why WebGL2 first

The renderer intentionally avoids Three.js, textures, video loops, model assets, and a post-processing framework. One fullscreen triangle + one procedural shader provides the depth/plasma/core/halo/particle look with a much smaller JS/runtime footprint. The Tauri host may later provide a WebGPU renderer behind the same event contract.

## Run the demo

From the repository root:

```bash
python -m http.server 8765 --directory .
```

Open `http://127.0.0.1:8765/renderer/orb/`.

The demo imports the canonical renderer from `ui/orb-renderer.js`; there is no second shader copy.

- Click: simulate user speech (energy travels inward).
- Shift+click: simulate AI speech (gold energy travels outward).
- Pointer movement: subtle 3D parallax.

## Host API

The Tauri/WebView host forwards backend events:

```js
window.metatronOrb.ingest({
  topic: "speech.user.level",
  payload: { level: 0.7 }
})
```

Useful methods:

```js
metatronOrb.setQuality("eco" | "balanced" | "spectacle")
metatronOrb.snapshot()
metatronOrb.setVisible(false)
```

High-rate amplitude events stay transient and must not be persisted.
