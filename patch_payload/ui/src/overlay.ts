// Unified overlay: EZSTT engine protocol + memory-light JARVIS HUD.

import { invoke } from "@tauri-apps/api/core";
import { mountJarvis } from "./jarvis-lite";
import {
  engineRequest,
  onEngineEvent,
  sessionStartedAt,
  type ConfigPayload,
  type StreamEvent,
  type StreamStatus,
} from "./shared/protocol";

declare global {
  interface Window {
    __ezstt_ping?: () => void;
  }
}

const pong = () => {
  void invoke("overlay_pong");
};
window.__ezstt_ping = pong;
pong();

const stage = document.getElementById("stage")!;
const hud = mountJarvis(stage);

function applyConfig(payload: ConfigPayload) {
  const cfg = payload.config ?? {};
  hud.setEnabled(cfg.overlay !== false);

  if (typeof cfg.silence_threshold === "number") {
    hud.setThreshold(cfg.silence_threshold);
  }

  const device = typeof cfg.device === "string" ? cfg.device : "";
  const model =
    typeof cfg.model === "string"
      ? cfg.model
      : payload.resolved?.model_dir ?? "";
  hud.setMeta(device, model);
}

onEngineEvent((e) => {
  if (e.event === "state") {
    hud.onState(String(e.state ?? "IDLE"), String(e.detail ?? ""));
  } else if (e.event === "level") {
    hud.setLevel(Number(e.value ?? 0));
  } else if (e.event === "config") {
    applyConfig(e as unknown as ConfigPayload);
  } else if (e.event === "stream") {
    const ev = e as StreamEvent;
    if (ev.kind === "started") {
      hud.setRecording(true, Date.now());
    } else if (ev.kind === "stopped" || ev.kind === "error") {
      hud.setRecording(false);
    }
  }
});

engineRequest<ConfigPayload>("get_config")
  .then(applyConfig)
  .catch(() => {});

engineRequest<StreamStatus>("stream_status", { text: false })
  .then((s) => {
    if (s.live) hud.setRecording(true, sessionStartedAt(s));
  })
  .catch(() => {});
