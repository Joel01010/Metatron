from pathlib import Path

import pytest

from metatron.settings import SettingsStore


ROOT = Path(__file__).resolve().parents[1]


class DummyDB:
    def __init__(self):
        self.d = {}

    def get_setting(self, key, default=None):
        return self.d.get(key, default)

    def set_setting(self, key, value):
        self.d[key] = value


def test_theme_presets_and_semantic_contract_are_present():
    js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    for theme in ("spectral-rose", "obsidian", "aurora", "ember", "porcelain"):
        assert f"'{theme}'" in js
    for token in (
        "--bg-base", "--surface-1", "--border-subtle", "--text-primary",
        "--accent-primary", "--intelligence-core", "--status-good",
        "--shadow-elevated", "--radius-lg", "--motion-normal",
    ):
        assert token in css
    assert "document.documentElement" in js and ".dataset.theme" in js
    assert 'id="presenceMemory"' in html
    assert 'id="presencePrivacy"' in html


def test_theme_import_is_allowlisted_and_has_no_css_injection_path():
    js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    assert "THEME_APPEARANCE_KEYS" in js
    assert "THEME_PRESENCE_KEYS" in js
    assert "Unknown appearance key" in js
    assert "Unknown presence key" in js
    assert "Theme must be a JSON object" in js
    assert "style.innerHTML" not in js
    assert "insertRule(" not in js
    assert "eval(" not in js


def test_theme_settings_validation_and_backward_compatibility():
    store = SettingsStore(DummyDB())
    app = store.get("appearance")
    assert app["theme"] == "spectral-rose"
    assert app["density"] == "comfortable"
    store.set("appearance", {"theme": "metatron"})  # legacy v1.4 ID remains accepted
    assert store.get("appearance")["theme"] == "metatron"
    with pytest.raises(ValueError, match="#RRGGBB"):
        store.set("appearance", {"accent": "red"})
    with pytest.raises(ValueError, match="between"):
        store.set("appearance", {"glow_strength": 2.0})
    with pytest.raises(ValueError, match="one of"):
        store.set("appearance", {"sidebar_mode": "floating"})


def test_reduced_motion_and_single_renderer_contracts():
    css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    orb = (ROOT / "ui" / "orb-renderer.js").read_text(encoding="utf-8")
    orb_bridge = (ROOT / "ui" / "orb.js").read_text(encoding="utf-8")
    assert 'data-reduce-motion="true"' in css
    assert "prefers-reduced-motion: reduce" in css
    assert "reduceMotion" in orb and "motionStyle" in orb
    assert "metatronEvent" in orb_bridge
    assert len(list(ROOT.rglob("orb-renderer.js"))) == 1
