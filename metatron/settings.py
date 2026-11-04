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
    "dictation": {
        "language": "en",
        "context_awareness": True,
        "dictionary_enabled": True,
        "history_days": 30,
        "history_max_items": 5000,
        "privacy_pause_enabled": True,
        "default_context_profile": "general",
    },
    "onboarding": {
        "completed": False,
        "show_tips": True,
        "last_completed_version": "",
    },
    "agents": {
        "confirm_local_launch": True,
        "confirm_cloud_launch": True,
        "auto_create_kanban": True,
        "max_local_coding_agents": 1,
    },
}


ENUMS = {
    ("presence", "quality"): {"eco", "balanced", "spectacle"},
    ("speech", "mode"): {"hold", "toggle", "always"},
    ("speech", "injection_method"): {"paste", "type", "clipboard"},
    ("voice", "tts_mode"): {"premium", "light", "off"},
    ("memory", "profile"): {"strict", "voice", "agent"},
    ("dictation", "default_context_profile"): {"general", "email", "work", "personal", "code", "terminal", "notes"},
}

RANGES = {
    ("presence", "orb_scale"): (0.5, 2.0),
    ("presence", "orb_opacity"): (0.1, 1.0),
    ("presence", "plasma"): (0.0, 1.5),
    ("presence", "particles"): (0.0, 1.5),
    ("presence", "bloom"): (0.0, 1.5),
    ("presence", "interaction_gain"): (0.1, 3.0),
    ("voice", "tts_speed"): (0.5, 2.0),
    ("voice", "tts_priority_threshold"): (0, 4),
    ("voice", "capture_tail_ms"): (0, 2000),
    ("agents", "max_local_coding_agents"): (0, 8),
    ("dictation", "history_days"): (1, 3650),
    ("dictation", "history_max_items"): (100, 100000),
}


def _validate_setting(section: str, key: str, value: Any, default: Any) -> Any:
    if isinstance(default, bool):
        if type(value) is not bool:
            raise TypeError(f"{section}.{key} must be boolean")
    elif isinstance(default, int) and not isinstance(default, bool):
        if type(value) is not int:
            raise TypeError(f"{section}.{key} must be integer")
    elif isinstance(default, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"{section}.{key} must be numeric")
        value = float(value)
    elif isinstance(default, str):
        if not isinstance(value, str):
            raise TypeError(f"{section}.{key} must be string")
    elif isinstance(default, list):
        if not isinstance(value, list):
            raise TypeError(f"{section}.{key} must be array")
    enum = ENUMS.get((section, key))
    if enum is not None and value not in enum:
        raise ValueError(f"{section}.{key} must be one of {sorted(enum)}")
    bounds = RANGES.get((section, key))
    if bounds is not None and not (bounds[0] <= value <= bounds[1]):
        raise ValueError(f"{section}.{key} must be between {bounds[0]} and {bounds[1]}")
    if (section, key) == ("hardware", "device_order"):
        # Product invariant: UI cannot reorder the hardware classes.
        if [str(x).upper() for x in value] != ["NPU", "GPU", "CPU"]:
            raise ValueError("hardware.device_order is fixed to NPU, GPU, CPU")
    return value


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
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise ValueError(f"unknown setting(s) in {section}: {', '.join(unknown)}")
        for key, value in values.items():
            target[key] = _validate_setting(section, key, value, allowed[key])
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
