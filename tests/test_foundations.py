from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from metatron.db import CURRENT_SCHEMA_VERSION, Database
from metatron.env import child_environment
from metatron.memory import ModelBroker, Reservation
from metatron.secret_store import MemorySecretStore


def test_db_migration_sets_user_version_and_creates_backup(tmp_path: Path):
    p = tmp_path / "legacy.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE legacy_marker(value TEXT)")
    con.execute("INSERT INTO legacy_marker VALUES('keep-me')")
    con.commit(); con.close()

    db = Database(p)
    try:
        assert db.schema_version == CURRENT_SCHEMA_VERSION
        assert db.query("SELECT value FROM legacy_marker")[0]["value"] == "keep-me"
        backups = list(tmp_path.glob("legacy.db.v0.backup-*"))
        assert backups, "existing legacy DB must be backed up before migration"
    finally:
        db.close()


def test_db_rejects_future_schema(tmp_path: Path):
    p = tmp_path / "future.db"
    con = sqlite3.connect(p)
    con.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION + 99}")
    con.close()
    with pytest.raises(RuntimeError, match="newer"):
        Database(p)


def test_child_env_does_not_leak_api_keys(monkeypatch):
    monkeypatch.setenv("SOME_API_KEY", "secret")
    monkeypatch.setenv("PATH", "/safe")
    env = child_environment()
    assert "SOME_API_KEY" not in env
    assert env.get("PATH") == "/safe"
    explicit = child_environment(extra={"METATRON_TEST_TOKEN": "ok"})
    assert explicit["METATRON_TEST_TOKEN"] == "ok"


def test_memory_secret_store_roundtrip():
    s = MemorySecretStore()
    s.set("x", "secret")
    assert s.get("x") == "secret"
    s.delete("x")
    assert s.get("x") is None


def test_placement_estimates_charge_worst_case_until_placement_known():
    b = ModelBroker(3000)
    b.register(Reservation("model", 100, placement_estimates_mib={"NPU": 300, "GPU": 500, "CPU": 900}))
    item = next(x for x in b.status()["resources"] if x["name"] == "model")
    assert item["charge_mib"] == 900
    b.set_placement("model", "GPU")
    item = next(x for x in b.status()["resources"] if x["name"] == "model")
    assert item["charge_mib"] == 500
