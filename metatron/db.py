from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator


SCHEMA = """
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


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        # Autocommit avoids a commit call for every read and allows explicit
        # transactions for multi-step mutations.
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)

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
