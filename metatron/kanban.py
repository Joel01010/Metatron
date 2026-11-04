from __future__ import annotations

import time
import uuid
from typing import Any

from .db import Database
from .events import EventBus

STATUSES = ("backlog", "ready", "running", "review", "blocked", "done")


class Kanban:
    def __init__(self, db: Database, bus: EventBus):
        self.db = db
        self.bus = bus

    def create(self, title: str, **kwargs: Any) -> dict[str, Any]:
        title = title.strip()
        if not title:
            raise ValueError("title required")
        status = kwargs.get("status", "backlog")
        if status not in STATUSES:
            raise ValueError(f"invalid status {status!r}")
        now = time.time()
        task_id = kwargs.get("id") or str(uuid.uuid4())
        self.db.execute(
            """INSERT INTO tasks(id,title,description,status,priority,project,agent_id,parent_id,
               scheduled_at,budget_json,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id, title, kwargs.get("description", ""), status,
                int(kwargs.get("priority", 0)), kwargs.get("project"), kwargs.get("agent_id"),
                kwargs.get("parent_id"), kwargs.get("scheduled_at"),
                self.db.dumps(kwargs.get("budget", {})), self.db.dumps(kwargs.get("metadata", {})),
                now, now,
            ),
        )
        self.bus.emit("task.created", "kanban", {"task_id": task_id, "status": status, "title": title})
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any]:
        rows = self.db.query("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not rows:
            raise KeyError(task_id)
        return self._decode(rows[0])

    def list(self, status: str | None = None, limit: int = 200, offset: int = 0) -> list[dict[str, Any]]:
        limit = min(max(1, int(limit)), 1000)
        offset = max(0, int(offset))
        if status:
            rows = self.db.query(
                "SELECT * FROM tasks WHERE status=? ORDER BY priority DESC,created_at LIMIT ? OFFSET ?",
                (status, limit, offset),
            )
        else:
            rows = self.db.query("SELECT * FROM tasks ORDER BY created_at LIMIT ? OFFSET ?", (limit, offset))
        return [self._decode(r) for r in rows]

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in STATUSES}
        for row in self.db.query("SELECT status,COUNT(*) AS n FROM tasks GROUP BY status"):
            if row["status"] in out:
                out[row["status"]] = int(row["n"])
        return out

    def move(self, task_id: str, status: str, actor: str = "user") -> dict[str, Any]:
        if status not in STATUSES:
            raise ValueError(f"invalid status {status!r}")
        before = self.get(task_id)
        self.db.execute("UPDATE tasks SET status=?,updated_at=? WHERE id=?", (status, time.time(), task_id))
        self.bus.emit("task.moved", actor, {"task_id": task_id, "from": before["status"], "to": status})
        return self.get(task_id)

    def assign(self, task_id: str, agent_id: str | None, actor: str = "user") -> dict[str, Any]:
        self.db.execute("UPDATE tasks SET agent_id=?,updated_at=? WHERE id=?", (agent_id, time.time(), task_id))
        self.bus.emit("task.assigned", actor, {"task_id": task_id, "agent_id": agent_id})
        return self.get(task_id)

    def _decode(self, row: dict[str, Any]) -> dict[str, Any]:
        row = dict(row)
        row["budget"] = self.db.loads(row.pop("budget_json"))
        row["metadata"] = self.db.loads(row.pop("metadata_json"))
        return row
