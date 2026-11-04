from __future__ import annotations

import threading
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

from .events import EventBus


class PresenceState(str, Enum):
    DORMANT = "dormant"
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    RESPONDING = "responding"
    SPEAKING = "speaking"


@dataclass(slots=True)
class PresenceSnapshot:
    state: str = PresenceState.IDLE.value
    user_level: float = 0.0
    ai_level: float = 0.0
    direction: str = "neutral"  # inward=user, outward=AI
    accent: str = "pale-red-gold"
    quality: str = "balanced"
    dashboard_open: bool = False
    updated_at: float = 0.0


class PresenceController:
    """Backend state machine for the procedural Metatron orb.

    The renderer is deliberately not implemented here. This controller emits
    visual semantics so a WebGPU/Tauri renderer can be replaced later without
    touching voice, agents, or scheduling.
    """

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._lock = threading.RLock()
        self._s = PresenceSnapshot(updated_at=time.time())

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._s)


    def renderer_packet(self) -> dict[str, Any]:
        """Compact renderer state for a Tauri/WebView host.

        High-rate levels still arrive through the ephemeral event ring; this
        packet is for cold start/reconnect and contains no animation history.
        """
        snap = self.snapshot()
        state_ids = {
            "dormant": 0, "idle": 1, "listening": 2, "transcribing": 3,
            "thinking": 4, "responding": 5, "speaking": 6,
        }
        return {
            "schema": 1,
            "state": snap["state"],
            "state_id": state_ids.get(snap["state"], 1),
            "user_level": snap["user_level"],
            "ai_level": snap["ai_level"],
            "direction": snap["direction"],
            "quality": snap["quality"],
            "accent": snap["accent"],
            "dashboard_open": snap["dashboard_open"],
        }

    def _state(self, state: PresenceState, *, source: str, reason: str = "") -> dict[str, Any]:
        with self._lock:
            self._s.state = state.value
            self._s.updated_at = time.time()
            if state not in (PresenceState.LISTENING, PresenceState.TRANSCRIBING):
                self._s.user_level = 0.0
            if state != PresenceState.SPEAKING:
                self._s.ai_level = 0.0
            if state == PresenceState.LISTENING:
                self._s.direction = "inward"
            elif state == PresenceState.SPEAKING:
                self._s.direction = "outward"
            else:
                self._s.direction = "neutral"
            snap = asdict(self._s)
        self.bus.emit("presence.state", source, {**snap, "reason": reason})
        return snap

    def set_quality(self, quality: str, *, source: str = "system") -> dict[str, Any]:
        q = str(quality).lower()
        if q not in {"eco", "balanced", "spectacle"}:
            raise ValueError("quality must be eco, balanced, or spectacle")
        with self._lock:
            self._s.quality = q
            self._s.updated_at = time.time()
            snap = asdict(self._s)
        self.bus.emit("presence.quality", source, {"quality": q})
        return snap

    def set_dashboard_open(self, opened: bool) -> dict[str, Any]:
        with self._lock:
            self._s.dashboard_open = bool(opened)
            self._s.updated_at = time.time()
            snap = asdict(self._s)
        # Frontend contract: desktop orb should enter reduced rendering while
        # dashboard is open, so two spectacle renderers don't run at full cost.
        self.bus.emit("presence.context", "ui", {
            "dashboard_open": bool(opened),
            "desktop_mode": "eco" if opened else "primary",
            "dashboard_mode": "primary" if opened else "off",
        })
        return snap

    def user_started(self) -> dict[str, Any]:
        self.bus.emit("speech.user.started", "voice", {})
        return self._state(PresenceState.LISTENING, source="voice", reason="user-speaking")

    def user_level(self, level: float) -> dict[str, Any]:
        v = max(0.0, min(1.0, float(level)))
        with self._lock:
            self._s.user_level = v
            self._s.direction = "inward"
            self._s.updated_at = time.time()
        payload = {
            "channel": "user", "level": v, "direction": "inward",
            "core": min(1.0, 0.25 + v * 0.75),
            "shell": min(1.0, 0.18 + v * 0.82),
            "particle_flow": "attract",
        }
        self.bus.emit_ephemeral("speech.user.level", "voice", payload)
        self.bus.emit_ephemeral("presence.level", "voice", payload)
        return payload

    def user_stopped(self) -> dict[str, Any]:
        self.bus.emit("speech.user.ended", "voice", {})
        return self._state(PresenceState.TRANSCRIBING, source="voice", reason="user-stopped")

    def asr_started(self) -> dict[str, Any]:
        self.bus.emit("asr.started", "voice", {})
        return self._state(PresenceState.TRANSCRIBING, source="voice", reason="asr")

    def asr_partial(self, text: str) -> None:
        self.bus.emit_ephemeral("asr.partial", "voice", {"text": str(text)[-500:]})

    def asr_completed(self, text: str = "") -> dict[str, Any]:
        self.bus.emit("asr.completed", "voice", {"text": str(text)[-2000:]})
        return self._state(PresenceState.IDLE, source="voice", reason="asr-complete")

    def thinking_started(self, source: str = "assistant") -> dict[str, Any]:
        self.bus.emit("assistant.thinking.started", source, {})
        return self._state(PresenceState.THINKING, source=source, reason="thinking")

    def thinking_finished(self, source: str = "assistant") -> dict[str, Any]:
        self.bus.emit("assistant.thinking.finished", source, {})
        return self._state(PresenceState.RESPONDING, source=source, reason="thinking-complete")

    def tts_started(self, provider: str, voice: str, duration_ms: float | None = None) -> dict[str, Any]:
        self.bus.emit("tts.started", "tts", {"provider": provider, "voice": voice, "duration_ms": duration_ms})
        return self._state(PresenceState.SPEAKING, source="tts", reason="tts")

    def tts_level(self, level: float, t_ms: float) -> dict[str, Any]:
        v = max(0.0, min(1.0, float(level)))
        with self._lock:
            self._s.ai_level = v
            self._s.direction = "outward"
            self._s.updated_at = time.time()
        payload = {
            "channel": "ai", "level": v, "t_ms": float(t_ms), "direction": "outward",
            "core": min(1.0, 0.35 + v * 0.65),
            "shell": min(1.0, 0.15 + v * 0.85),
            "particle_flow": "radiate",
        }
        self.bus.emit_ephemeral("tts.level", "tts", payload)
        self.bus.emit_ephemeral("presence.level", "tts", payload)
        return payload

    def tts_finished(self, *, stopped: bool = False) -> dict[str, Any]:
        self.bus.emit("tts.finished", "tts", {"stopped": bool(stopped)})
        return self._state(PresenceState.IDLE, source="tts", reason="tts-finished")

    def signal(self, kind: str, message: str = "", *, source: str = "system") -> None:
        kind = str(kind).lower()
        if kind not in {"success", "warning", "error", "approval"}:
            raise ValueError("unsupported presence signal")
        self.bus.emit(f"system.{kind}", source, {"message": str(message)[:1000]})
        self.bus.emit("presence.signal", source, {"kind": kind, "message": str(message)[:500]})
