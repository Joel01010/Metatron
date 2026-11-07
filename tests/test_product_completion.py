from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import pytest

from metatron.agents.base import AgentState, AgentStatus
from metatron.config import AppConfig
from metatron.core import Metatron
from metatron.db import Database
from metatron.events import EventBus
from metatron.scheduler import Scheduler
from metatron.settings import DEFAULT_PETS, SettingsStore

ROOT = Path(__file__).resolve().parents[1]


class DummyDB:
    def __init__(self):
        self.d = {}

    def get_setting(self, key, default=None):
        return self.d.get(key, default)

    def set_setting(self, key, value):
        self.d[key] = value


class FakeEzra:
    id = "ezra"
    label = "Fake Ezra"
    kind = "test-remote"

    def __init__(self):
        self.submitted: list[dict] = []
        self.cancelled: list[str | None] = []

    def detect(self):
        return {"available": True}

    def status(self):
        return AgentStatus(self.id, self.label, self.kind, AgentState.IDLE, "ready")

    def start(self):
        return self.status()

    def stop(self):
        return self.status()

    def submit(self, task):
        self.submitted.append(dict(task))
        return {"accepted": True, "job_id": "job-product-1"}

    def job_status(self, job_id=None):
        return {"job_id": job_id, "state": "completed"}

    def cancel_job(self, job_id=None):
        self.cancelled.append(job_id)
        return {"cancelled": True, "job_id": job_id}


def test_presence_and_companion_defaults_are_complete_and_bounded():
    settings = SettingsStore(DummyDB()).all()
    presence = settings["presence"]
    companions = settings["companions"]

    assert presence["mode"] == "orb"
    assert presence["core_style"] in {"solar", "lattice", "reactor"}
    assert presence["desktop_pets"] is True
    assert presence["dashboard_pets"] is True
    assert presence["click_through"] is False
    assert companions["performance_policy"] == "adaptive"
    assert [p["form"] for p in companions["pets"]] == ["flin", "wisp", "drone", "mote"]
    assert len(companions["pets"]) == 4


def test_companion_settings_validate_multiple_independent_pets():
    store = SettingsStore(DummyDB())
    pets = [dict(DEFAULT_PETS[0]), dict(DEFAULT_PETS[1])]
    pets[0].update({"enabled": True, "behavior": "pointer", "size": 1.25})
    pets[1].update({"enabled": True, "skin": "frost", "anchor": "lower-right"})

    saved = store.set("companions", {"enabled": True, "pets": pets})
    assert saved["enabled"] is True
    assert saved["pets"][0]["behavior"] == "pointer"
    assert saved["pets"][0]["size"] == 1.25
    assert saved["pets"][1]["skin"] == "frost"

    with pytest.raises(ValueError, match="at most four"):
        store.set("companions", {"pets": [dict(DEFAULT_PETS[0])] * 5})

    duplicate = [dict(DEFAULT_PETS[0]), dict(DEFAULT_PETS[1])]
    duplicate[1]["id"] = duplicate[0]["id"]
    with pytest.raises(ValueError, match="unique"):
        store.set("companions", {"pets": duplicate})

    invalid = [dict(DEFAULT_PETS[0])]
    invalid[0]["primary"] = "red"
    with pytest.raises(ValueError, match="#RRGGBB"):
        store.set("companions", {"pets": invalid})

    invalid = [dict(DEFAULT_PETS[0])]
    invalid[0]["form"] = "copyrighted-mascot"
    with pytest.raises(ValueError, match="form"):
        store.set("companions", {"pets": invalid})



def test_legacy_single_pet_settings_migrate_without_importing_asset_paths():
    db = DummyDB()
    db.set_setting("app.settings", {"presence": {"pet_enabled": True, "pet_skin": "frost"}})
    migrated = SettingsStore(db).all()
    assert migrated["presence"]["mode"] == "both"
    assert migrated["companions"]["enabled"] is True
    assert migrated["companions"]["pets"][0]["enabled"] is True
    assert migrated["companions"]["pets"][0]["skin"] == "frost"

    db.set_setting("app.settings", {"presence": {"pet_enabled": True, "pet_skin": r"C:\\Users\\me\\character.png"}})
    safe = SettingsStore(db).all()
    assert safe["companions"]["pets"][0]["skin"] == "spectral"

def test_presence_core_styles_and_dynamics_are_validated():
    store = SettingsStore(DummyDB())
    saved = store.set("presence", {
        "mode": "both",
        "core_style": "reactor",
        "core_pulse": 1.2,
        "core_rotation": 1.4,
        "core_complexity": 1.1,
        "core_shell": 0.9,
        "trail_strength": 0.8,
        "parallax_strength": 0.7,
    })
    assert saved["mode"] == "both"
    assert saved["core_style"] == "reactor"
    with pytest.raises(ValueError):
        store.set("presence", {"core_style": "unknown"})
    with pytest.raises(ValueError, match="between"):
        store.set("presence", {"core_pulse": 99})


def test_scheduler_can_pause_resume_and_delete_without_drift_contract_change():
    with tempfile.TemporaryDirectory() as td:
        db = Database(Path(td) / "m.db")
        try:
            scheduler = Scheduler(db, EventBus(db))
            item = scheduler.create_interval("daily", {"title": "Daily task"}, 60, first_run=100)
            paused = scheduler.set_enabled(item["id"], False)
            assert int(paused["enabled"]) == 0
            assert scheduler.due(1000) == []
            resumed = scheduler.set_enabled(item["id"], True)
            assert int(resumed["enabled"]) == 1
            assert scheduler.delete(item["id"]) is True
            with pytest.raises(KeyError):
                scheduler.get(item["id"])
        finally:
            db.close()


def test_explicit_task_run_persists_and_reconciles_remote_completion():
    with tempfile.TemporaryDirectory() as td:
        app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False, tts_enabled=False))
        try:
            fake = FakeEzra()
            app.agents._agents["ezra"] = fake
            task = app.kanban.create(
                "Ship full product", description="explicit run only", status="ready", agent_id="ezra"
            )
            launched = app.run_task(task["id"])
            run = launched["run"]
            assert run["state"] == "running"
            assert run["metadata"]["submission"]["job_id"] == "job-product-1"
            assert app.kanban.get(task["id"])["status"] == "running"
            assert fake.submitted and fake.submitted[0]["id"] == task["id"]

            reconciled = app.refresh_run(run["id"])
            assert reconciled["state"] == "succeeded"
            assert app.kanban.get(task["id"])["status"] == "review"
        finally:
            app.close()


def test_schedules_materialize_ready_cards_but_do_not_auto_execute_agents():
    with tempfile.TemporaryDirectory() as td:
        app = Metatron(AppConfig(data_dir=Path(td), enable_background_maintenance=False, tts_enabled=False))
        try:
            fake = FakeEzra()
            app.agents._agents["ezra"] = fake
            sched = app.scheduler.create_interval(
                "Scheduled review", {"title": "Scheduled review"}, 60, agent_id="ezra", first_run=100
            )
            created = app._materialize_due_schedules(100)
            assert len(created) == 1
            assert created[0]["status"] == "ready"
            assert created[0]["agent_id"] == "ezra"
            assert created[0]["metadata"]["schedule_id"] == sched["id"]
            assert fake.submitted == []
        finally:
            app.close()


def test_full_product_ui_contains_core_companions_automation_and_search():
    html = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "ui" / "app.js").read_text(encoding="utf-8")
    renderer = (ROOT / "ui" / "orb-renderer.js").read_text(encoding="utf-8")
    orb_html = (ROOT / "ui" / "orb.html").read_text(encoding="utf-8")

    assert "orb.html?dashboard=1" in html
    assert 'id="settingsSearch"' in html
    assert 'data-presence-choice="orb"' in html
    assert 'data-presence-choice="pet"' in html
    assert 'data-presence-choice="both"' in html
    assert 'class="automation-grid"' in html and 'id="scheduleList"' in html and 'id="runList"' in html
    assert "syncPresenceWindow" in app_js
    assert "!!p.click_through,Number(p.orb_scale||1)" in app_js
    assert "orb.ignore_cursor" in app_js
    assert "presenceStudioMarkup" in app_js
    assert "petEditorMarkup" in app_js
    assert "run.refresh" in app_js and "run.cancel" in app_js
    for form in ("flin", "wisp", "drone", "mote"):
        # Forms are renderer data consumed by the procedural CSS layer. Flin is
        # the default body style; the other forms override it explicitly.
        if form == "flin":
            assert "pet.form||'flin'" in renderer and ".pet-body" in orb_html
        else:
            assert f'data-form="{form}"' in orb_html
    for style in ("solar", "lattice", "reactor"):
        assert style in renderer
    assert "uCoreStyle" in renderer
    assert "uCorePulse" in renderer
    assert "uCoreRotation" in renderer
    assert "memory.pressure" in renderer
    assert "Companion-only fallback" in renderer
    assert "model.reduceMotion||model.motionStyle==='minimal'" in renderer


def test_native_shell_has_tray_hidden_presence_startup_and_same_35_command_boundary():
    rust = (ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    cfg = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    probe = (ROOT / "scripts" / "Test-OrbWindow.ps1").read_text(encoding="utf-8")

    assert "TrayIconBuilder" in rust
    assert "set_ignore_cursor_events" in rust and "orb.ignore_cursor" in rust
    assert "Open Dashboard" in rust
    assert "Show / Hide Presence" in rust
    assert "Quit Metatron" in rust
    orb_cfg = next(w for w in cfg["app"]["windows"] if w.get("label") == "orb")
    assert orb_cfg["visible"] is False
    assert orb_cfg["resizable"] is False
    assert "ShowWindow" in probe and "SW_SHOWNA" in probe
    assert "ScreenshotPath" in probe and "CopyFromScreen" in probe
    assert "deterministic_anchor=$anchored" in probe

    body = re.search(
        r"fn\s+main_allowed\s*\(cmd:\s*&str\)\s*->\s*bool\s*\{\s*matches!\(\s*cmd\s*,(.*?)\)\s*\}",
        rust,
        re.S,
    )
    assert body
    allowed = set(re.findall(r'"([A-Za-z0-9_.-]+)"', body.group(1)))
    assert len(allowed) == 35
    assert {"tasks.list", "tasks.create", "tasks.move"}.issubset(allowed)
    assert "automation.manage" not in allowed


def test_dashboard_automation_reuses_authorized_task_contract_instead_of_widening_surface():
    server = (ROOT / "metatron" / "server.py").read_text(encoding="utf-8")
    assert 'cmd == "tasks.list"' in server and 'p.get("automation")' in server
    assert 'cmd == "tasks.create"' in server and 'p.get("entity") == "schedule"' in server
    for action in (
        "assign", "run", "run.refresh", "run.cancel",
        "schedule.toggle", "schedule.delete", "approval.decide",
    ):
        assert f'"{action}"' in server
