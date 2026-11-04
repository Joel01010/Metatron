from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "appearance": {
        "theme": "metatron",
        "accent": "#ff9c9c",
        "gold": "#ffc857",
        "background": "#090708",
        "density": "comfortable",
        "reduce_motion": False,
    },
    "presence": {
        "enabled": True,
        "quality": "balanced",
        "desktop_orb": True,
        "dashboard_orb": True,
        "always_on_top": True,
        "orb_scale": 1.0,
        "orb_opacity": 0.96,
        "plasma": 0.82,
        "particles": 0.78,
        "bloom": 0.88,
        "interaction_gain": 1.0,
        "pet_enabled": False,
        "pet_skin": "",
    },
    "speech": {
        "enabled": True,
        "auto_start": False,
        "model": "parakeet-unified-en-0.6b",
        "hotkey": "right ctrl",
        "mode": "hold",
        "injection_method": "paste",
        "cleanup_enabled": True,
    },
    "voice": {
        "tts_enabled": True,
        "tts_mode": "premium",
        "tts_voice": "am_fenrir",
        "tts_speed": 0.96,
        "tts_priority_threshold": 3,
        "barge_in": True,
        "echo_guard": True,
        "capture_tail_ms": 280,
        "cleanup_enabled": True,
    },
    "hardware": {
        "device_order": ["NPU", "GPU", "CPU"],
        "all_npus": True,
        "gpu_fallback": True,
        "allow_cpu_fallback": True,
        "auto_reduce_visuals": True,
        "prefer_low_power": True,
    },
    "memory": {
        "profile": "strict",
        "adaptive_pressure": True,
    },
    "privacy": {
        "telemetry_local_only": True,
        "save_transcripts": False,
        "save_audio": False,
        "cloud_context_default": False,
    },
    "agents": {
        "confirm_local_launch": True,
        "confirm_cloud_launch": True,
        "auto_create_kanban": True,
        "max_local_coding_agents": 1,
    },
}


class SettingsStore:
    def __init__(self, db: Any, bus: Any | None = None):
        self.db = db
        self.bus = bus

    def all(self) -> dict[str, Any]:
        saved = self.db.get_setting("app.settings", {}) or {}
        return self._merge(deepcopy(DEFAULT_SETTINGS), saved if isinstance(saved, dict) else {})

    def get(self, section: str | None = None) -> Any:
        data = self.all()
        return data if not section else deepcopy(data.get(str(section), {}))

    def set(self, section: str, values: dict[str, Any]) -> dict[str, Any]:
        section = str(section)
        if section not in DEFAULT_SETTINGS:
            raise ValueError(f"unknown settings section {section!r}")
        if not isinstance(values, dict):
            raise TypeError("settings values must be an object")
        data = self.all()
        allowed = DEFAULT_SETTINGS[section]
        target = dict(data.get(section) or {})
        for key, value in values.items():
            if key in allowed:
                target[key] = value
        data[section] = target
        self.db.set_setting("app.settings", data)
        if self.bus is not None:
            self.bus.emit("settings.changed", "user", {"section": section, "values": target})
        return deepcopy(target)

    def reset(self, section: str | None = None) -> dict[str, Any]:
        data = self.all()
        if section is None:
            data = deepcopy(DEFAULT_SETTINGS)
        else:
            if section not in DEFAULT_SETTINGS:
                raise ValueError(f"unknown settings section {section!r}")
            data[section] = deepcopy(DEFAULT_SETTINGS[section])
        self.db.set_setting("app.settings", data)
        if self.bus is not None:
            self.bus.emit("settings.reset", "user", {"section": section})
        return deepcopy(data if section is None else data[section])

    @classmethod
    def _merge(cls, base: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
        for key, value in other.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = cls._merge(base[key], value)
            elif key in base:
                base[key] = deepcopy(value)
        return base
