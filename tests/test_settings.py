from __future__ import annotations

import pytest

from metatron.settings import SettingsStore


class DummyDB:
    def __init__(self): self.d = {}
    def get_setting(self, key, default=None): return self.d.get(key, default)
    def set_setting(self, key, value): self.d[key] = value


def test_defaults_and_persistence():
    db = DummyDB(); s = SettingsStore(db)
    assert s.all()["hardware"]["device_order"] == ["NPU", "GPU", "CPU"]
    s.set("appearance", {"accent": "#123456"})
    assert s.get("appearance")["accent"] == "#123456"


def test_unknown_settings_rejected():
    s = SettingsStore(DummyDB())
    with pytest.raises(ValueError, match="unknown setting"):
        s.set("appearance", {"not_allowed": True})


def test_fixed_hardware_order_and_ranges():
    s = SettingsStore(DummyDB())
    with pytest.raises(ValueError, match="fixed"):
        s.set("hardware", {"device_order": ["GPU", "NPU", "CPU"]})
    with pytest.raises(ValueError, match="between"):
        s.set("presence", {"orb_opacity": 5.0})
    with pytest.raises(TypeError, match="boolean"):
        s.set("voice", {"tts_enabled": "yes"})


def test_reset_section():
    db = DummyDB(); s = SettingsStore(db)
    s.set("presence", {"quality": "eco"})
    assert s.reset("presence")["quality"] == "balanced"
