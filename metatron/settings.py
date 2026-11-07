from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_PETS: list[dict[str, Any]] = [
    {
        "id": "flin", "name": "Flin", "enabled": False, "form": "flin",
        "skin": "spectral", "behavior": "orbit", "anchor": "free",
        "primary": "#ff8f9c", "secondary": "#ffc65c",
        "size": 1.0, "energy": 0.78, "voice_reactivity": 0.85,
        "task_reactivity": 0.65,
    },
    {
        "id": "wisp", "name": "Wisp", "enabled": False, "form": "wisp",
        "skin": "lumen", "behavior": "drift", "anchor": "upper-right",
        "primary": "#78d9ff", "secondary": "#c8a7ff",
        "size": 0.92, "energy": 0.62, "voice_reactivity": 0.75,
        "task_reactivity": 0.55,
    },
    {
        "id": "drone", "name": "Drone", "enabled": False, "form": "drone",
        "skin": "graphite", "behavior": "perch", "anchor": "lower-left",
        "primary": "#d9e0e8", "secondary": "#ffb34e",
        "size": 0.86, "energy": 0.50, "voice_reactivity": 0.55,
        "task_reactivity": 0.90,
    },
    {
        "id": "mote", "name": "Mote", "enabled": False, "form": "mote",
        "skin": "ember", "behavior": "pointer", "anchor": "free",
        "primary": "#ff8b6e", "secondary": "#ffd56a",
        "size": 0.72, "energy": 0.88, "voice_reactivity": 0.95,
        "task_reactivity": 0.45,
    },
]


DEFAULT_SETTINGS: dict[str, Any] = {
    "appearance": {
        "theme": "spectral-rose",
        "accent": "#ff8f9c",
        "gold": "#ffc65c",
        "background": "#080607",
        "surface_tint": "#171014",
        "material_strength": 0.70,
        "border_strength": 0.54,
        "glow_strength": 0.78,
        "radius_style": "soft",
        "font_scale": 1.0,
        "density": "comfortable",
        "motion_style": "balanced",
        "sidebar_mode": "full",
        "reduce_motion": False,
    },
    "presence": {
        "enabled": True,
        "quality": "balanced",
        "desktop_orb": True,
        "dashboard_orb": True,
        "always_on_top": True,
        "click_through": False,
        "orb_scale": 1.0,
        "orb_opacity": 0.96,
        "plasma": 0.82,
        "particles": 0.78,
        "bloom": 0.88,
        "interaction_gain": 1.0,
        "mode": "orb",
        "core_style": "solar",
        "core_pulse": 0.76,
        "core_rotation": 0.55,
        "core_complexity": 0.82,
        "core_shell": 0.72,
        "trail_strength": 0.36,
        "parallax_strength": 0.68,
        "desktop_pets": True,
        "dashboard_pets": True,
        # Legacy keys are retained so existing v1.4 settings migrate safely.
        "pet_enabled": False,
        "pet_skin": "",
    },
    "companions": {
        "enabled": False,
        "reaction_gain": 1.0,
        "pointer_interaction": True,
        "performance_policy": "adaptive",
        "pets": deepcopy(DEFAULT_PETS),
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
    "dashboard": {
        "home_stack_order": ["dictation", "memory", "quick-actions"],
        "overview_order": ["workflow", "activity", "agents"],
        "hidden_widgets": [],
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
    ("appearance", "theme"): {"metatron", "spectral-rose", "obsidian", "aurora", "ember", "porcelain", "custom"},
    ("appearance", "density"): {"compact", "comfortable", "spacious"},
    ("appearance", "radius_style"): {"crisp", "balanced", "soft"},
    ("appearance", "motion_style"): {"minimal", "balanced", "expressive"},
    ("appearance", "sidebar_mode"): {"full", "compact"},
    ("presence", "quality"): {"eco", "balanced", "spectacle"},
    ("presence", "mode"): {"orb", "pet", "both"},
    ("presence", "core_style"): {"solar", "lattice", "reactor"},
    ("companions", "performance_policy"): {"adaptive", "full", "minimal"},
    ("speech", "mode"): {"hold", "toggle"},
    ("speech", "injection_method"): {"paste", "type"},
    ("voice", "tts_mode"): {"premium", "light", "off"},
    ("memory", "profile"): {"strict", "voice", "agent"},
    ("dictation", "default_context_profile"): {"general", "email", "work", "personal", "code", "terminal", "notes"},
}

RANGES = {
    ("appearance", "material_strength"): (0.0, 1.0),
    ("appearance", "border_strength"): (0.0, 1.0),
    ("appearance", "glow_strength"): (0.0, 1.0),
    ("appearance", "font_scale"): (0.85, 1.2),
    ("presence", "orb_scale"): (0.5, 2.0),
    ("presence", "orb_opacity"): (0.1, 1.0),
    ("presence", "plasma"): (0.0, 1.5),
    ("presence", "particles"): (0.0, 1.5),
    ("presence", "bloom"): (0.0, 1.5),
    ("presence", "interaction_gain"): (0.1, 3.0),
    ("presence", "core_pulse"): (0.0, 2.0),
    ("presence", "core_rotation"): (0.0, 2.0),
    ("presence", "core_complexity"): (0.0, 1.5),
    ("presence", "core_shell"): (0.0, 1.5),
    ("presence", "trail_strength"): (0.0, 1.5),
    ("presence", "parallax_strength"): (0.0, 1.5),
    ("companions", "reaction_gain"): (0.0, 2.0),
    ("voice", "tts_speed"): (0.5, 2.0),
    ("voice", "tts_priority_threshold"): (0, 4),
    ("voice", "capture_tail_ms"): (0, 2000),
    ("agents", "max_local_coding_agents"): (0, 8),
    ("dictation", "history_days"): (1, 3650),
    ("dictation", "history_max_items"): (100, 100000),
}


COLOR_KEYS = {
    ("appearance", "accent"),
    ("appearance", "gold"),
    ("appearance", "background"),
    ("appearance", "surface_tint"),
}


def _validate_hex_color(value: str, label: str) -> str:
    if len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"{label} must be a #RRGGBB color")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ValueError(f"{label} must be a #RRGGBB color") from exc
    return value.lower()


PET_ENUMS = {
    "form": {"flin", "wisp", "drone", "mote"},
    "skin": {"spectral", "lumen", "graphite", "ember", "frost", "rose", "custom"},
    "behavior": {"orbit", "drift", "perch", "pointer"},
    "anchor": {"free", "upper-left", "upper-right", "lower-left", "lower-right"},
}
PET_RANGES = {"size": (0.45, 1.6), "energy": (0.0, 1.5), "voice_reactivity": (0.0, 1.5), "task_reactivity": (0.0, 1.5)}

def _validate_pet_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise TypeError("companions.pets must be array")
    if len(value) > 4:
        raise ValueError("companions.pets supports at most four companions")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed = {"id", "name", "enabled", "form", "skin", "behavior", "anchor", "primary", "secondary", *PET_RANGES}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise TypeError(f"companions.pets[{index}] must be object")
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise ValueError(f"unknown companion key: {unknown[0]}")
        pet = dict(DEFAULT_PETS[index] if index < len(DEFAULT_PETS) else DEFAULT_PETS[0])
        pet.update(raw)
        pid = str(pet.get("id") or "").strip().lower()
        if not pid or len(pid) > 24 or not all(c.isalnum() or c in "-_" for c in pid):
            raise ValueError("companion id must be 1-24 letters, numbers, '-' or '_'")
        if pid in seen:
            raise ValueError("companion ids must be unique")
        seen.add(pid); pet["id"] = pid
        name = str(pet.get("name") or "").strip()
        if not name or len(name) > 40:
            raise ValueError("companion name must be 1-40 characters")
        pet["name"] = name
        if type(pet.get("enabled")) is not bool:
            raise TypeError("companion enabled must be boolean")
        for key, choices in PET_ENUMS.items():
            if pet.get(key) not in choices:
                raise ValueError(f"companion {key} must be one of {sorted(choices)}")
        for key in ("primary", "secondary"):
            pet[key] = _validate_hex_color(str(pet.get(key) or ""), f"companion {key}")
        for key, bounds in PET_RANGES.items():
            raw_value = pet.get(key)
            if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
                raise TypeError(f"companion {key} must be numeric")
            number = float(raw_value)
            if not (bounds[0] <= number <= bounds[1]):
                raise ValueError(f"companion {key} must be between {bounds[0]} and {bounds[1]}")
            pet[key] = number
        out.append(pet)
    return out


def _validate_setting(section: str, key: str, value: Any, default: Any) -> Any:
    if (section, key) == ("companions", "pets"):
        return _validate_pet_list(value)
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
    if (section, key) in COLOR_KEYS:
        value = _validate_hex_color(value, f"{section}.{key}")
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
    if section == "dashboard":
        allowed_widgets = {"dictation", "memory", "quick-actions", "workflow", "activity", "agents"}
        if key == "home_stack_order":
            expected = {"dictation", "memory", "quick-actions"}
            if len(value) != len(set(value)) or set(value) != expected:
                raise ValueError("dashboard.home_stack_order must contain each primary widget exactly once")
        elif key == "overview_order":
            expected = {"workflow", "activity", "agents"}
            if len(value) != len(set(value)) or set(value) != expected:
                raise ValueError("dashboard.overview_order must contain each overview widget exactly once")
        elif key == "hidden_widgets":
            if len(value) != len(set(value)) or any(str(x) not in allowed_widgets for x in value):
                raise ValueError("dashboard.hidden_widgets contains an unknown or duplicate widget")
    return value


class SettingsStore:
    def __init__(self, db: Any, bus: Any | None = None):
        self.db = db
        self.bus = bus

    def all(self) -> dict[str, Any]:
        saved = self.db.get_setting("app.settings", {}) or {}
        saved = saved if isinstance(saved, dict) else {}
        merged = self._merge(deepcopy(DEFAULT_SETTINGS), saved)

        # Read-time compatibility for the pre-roster v1.4 pet switch.  The old
        # setting could point at arbitrary artwork; the new product only maps
        # recognized built-in skin names and never imports a legacy file path.
        legacy_presence = saved.get("presence") if isinstance(saved.get("presence"), dict) else {}
        if legacy_presence.get("pet_enabled") is True and "companions" not in saved:
            merged["companions"]["enabled"] = True
            merged["companions"]["pets"][0]["enabled"] = True
            if "mode" not in legacy_presence:
                merged["presence"]["mode"] = "both"
            legacy_skin = str(legacy_presence.get("pet_skin") or "").strip().lower()
            if legacy_skin in PET_ENUMS["skin"]:
                merged["companions"]["pets"][0]["skin"] = legacy_skin
        return merged

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
