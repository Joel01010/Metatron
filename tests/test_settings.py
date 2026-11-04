from __future__ import annotations

from metatron.settings import SettingsStore


class DummyDB:
    def __init__(self): self.d = {}
    def get_setting(self, key, default=None): return self.d.get(key, default)
    def set_setting(self, key, value): self.d[key] = value


def test_defaults_and_persistence():
    db = DummyDB(); s = SettingsStore(db)
    assert s.all()["hardware"]["device_order"] == ["NPU", "GPU", "CPU"]
    s.set("appearance", {"accent": "#123456", "not_allowed": True})
    assert s.get("appearance")["accent"] == "#123456"
    assert "not_allowed" not in s.get("appearance")


def test_reset_section():
    db = DummyDB(); s = SettingsStore(db)
    s.set("presence", {"quality": "eco"})
    assert s.reset("presence")["quality"] == "balanced"
