from __future__ import annotations

import json
import sqlite3
import threading
import time
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator


CURRENT_SCHEMA_VERSION = 2

SCHEMA_V1 = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=3000;
PRAGMA cache_size=-2048;

CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  transport TEXT NOT NULL,
  endpoint TEXT,
  config_json TEXT NOT NULL DEFAULT '{}',
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 0,
  project TEXT,
  agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  parent_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  scheduled_at REAL,
  budget_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS task_runs (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  state TEXT NOT NULL,
  lease_owner TEXT,
  lease_expires REAL,
  started_at REAL,
  finished_at REAL,
  exit_code INTEGER,
  usage_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL,
  expires_at REAL,
  created_at REAL NOT NULL,
  decided_at REAL
);

CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  topic TEXT NOT NULL,
  source TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  agent_id TEXT REFERENCES agents(id) ON DELETE SET NULL,
  task_template_json TEXT NOT NULL,
  interval_s REAL,
  next_run REAL NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  source TEXT NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL DEFAULT '',
  labels_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_runs_task ON task_runs(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_task_runs_lease ON task_runs(state, lease_expires);
CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry(ts);
"""

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS dictation_history (
  id TEXT PRIMARY KEY,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL,
  raw_text TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL DEFAULT '',
  app_id TEXT NOT NULL DEFAULT '',
  app_name TEXT NOT NULL DEFAULT '',
  context_profile TEXT NOT NULL DEFAULT 'general',
  language TEXT NOT NULL DEFAULT 'en',
  model TEXT NOT NULL DEFAULT '',
  device_kind TEXT NOT NULL DEFAULT '',
  provider TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'completed',
  duration_ms REAL,
  error TEXT NOT NULL DEFAULT '',
  pinned INTEGER NOT NULL DEFAULT 0,
  audio_path TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS vocabulary (
  id TEXT PRIMARY KEY,
  term TEXT NOT NULL COLLATE NOCASE,
  replacement TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  usage_count INTEGER NOT NULL DEFAULT 0,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS app_rules (
  app_id TEXT PRIMARY KEY COLLATE NOCASE,
  label TEXT NOT NULL DEFAULT '',
  privacy_action TEXT NOT NULL DEFAULT 'allow',
  context_profile TEXT NOT NULL DEFAULT 'general',
  enabled INTEGER NOT NULL DEFAULT 1,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dictation_history_created ON dictation_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dictation_history_app ON dictation_history(app_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_dictation_history_status ON dictation_history(status, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_vocabulary_term ON vocabulary(term COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_app_rules_action ON app_rules(privacy_action);
"""

MIGRATIONS = {1: SCHEMA_V1, 2: SCHEMA_V2}


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Autocommit avoids a commit call for every read and allows explicit
        # transactions for multi-step mutations.
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        try:
            with self._lock:
                self._migrate_locked()
        except Exception:
            # Constructor failures must not leak an open SQLite handle. This is
            # particularly important when rejecting a future schema version.
            self._conn.close()
            raise


    def _user_version_locked(self) -> int:
        row = self._conn.execute("PRAGMA user_version").fetchone()
        return int(row[0] if row else 0)

    def _backup_before_migration(self, from_version: int) -> Path | None:
        # Fresh databases need no backup. Existing DBs are copied before any
        # schema mutation so an interrupted upgrade is recoverable.
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        target = self.path.with_name(f"{self.path.name}.v{from_version}.backup-{stamp}")
        # SQLite backup API gives a consistent copy even in WAL mode.
        dst = sqlite3.connect(target)
        try:
            self._conn.backup(dst)
        finally:
            dst.close()
        return target

    def _migrate_locked(self) -> None:
        version = self._user_version_locked()
        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"database schema v{version} is newer than this Metatron build (v{CURRENT_SCHEMA_VERSION})"
            )
        if version < CURRENT_SCHEMA_VERSION:
            has_user_tables = bool(self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
            ).fetchone())
            if has_user_tables:
                self._backup_before_migration(version)
            for target in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
                script = MIGRATIONS.get(target)
                if script is None:
                    raise RuntimeError(f"missing database migration for schema v{target}")
                self._conn.executescript(script)
                self._conn.execute(f"PRAGMA user_version={target}")
        else:
            self._conn.executescript(MIGRATIONS[CURRENT_SCHEMA_VERSION])

    @property
    def schema_version(self) -> int:
        with self._lock:
            return self._user_version_locked()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            finally:
                self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def executemany(self, sql: str, rows: Iterable[Iterable[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.executemany(sql, rows)

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def loads(raw: str | None) -> Any:
        return json.loads(raw or "{}")

    def append_event(self, topic: str, source: str, payload: dict[str, Any]) -> int:
        cur = self.execute(
            "INSERT INTO events(ts,topic,source,payload_json) VALUES(?,?,?,?)",
            (time.time(), topic, source, self.dumps(payload)),
        )
        return int(cur.lastrowid)

    def get_setting(self, key: str, default: Any = None) -> Any:
        rows = self.query("SELECT value_json FROM settings WHERE key=?", (str(key),))
        if not rows:
            return default
        try:
            return self.loads(rows[0]["value_json"])
        except Exception:
            return default

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            """INSERT INTO settings(key,value_json,updated_at) VALUES(?,?,?)
               ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at""",
            (str(key), self.dumps(value), time.time()),
        )

    def prune_events(self, keep: int = 10_000) -> int:
        keep = max(100, int(keep))
        cur = self.execute(
            "DELETE FROM events WHERE seq < (SELECT COALESCE(MAX(seq),0)-? FROM events)",
            (keep,),
        )
        return int(cur.rowcount if cur.rowcount is not None else 0)
