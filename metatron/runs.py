from __future__ import annotations

import time
import uuid
from typing import Any

from .db import Database
from .events import EventBus

RUN_STATES = ("queued", "leased", "running", "waiting", "review", "succeeded", "failed", "cancelled")


class RunStore:
    """Persistent execution records with expiring leases.

    A lease prevents two agent workers from accidentally running the same card.
    """

    def __init__(self, db: Database, bus: EventBus):
        self.db = db
        self.bus = bus

    def create(self, task_id: str, agent_id: str | None = None, metadata: dict[str, Any] | None = None) -> dict:
        rid = str(uuid.uuid4())
        now = time.time()
        self.db.execute(
            """INSERT INTO task_runs(id,task_id,agent_id,state,metadata_json,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?)""",
            (rid, task_id, agent_id, "queued", self.db.dumps(metadata or {}), now, now),
        )
        self.bus.emit("run.created", "runs", {"run_id": rid, "task_id": task_id, "agent_id": agent_id})
        return self.get(rid)

    def get(self, run_id: str) -> dict:
        rows = self.db.query("SELECT * FROM task_runs WHERE id=?", (run_id,))
        if not rows:
            raise KeyError(run_id)
        row = rows[0]
        row["usage"] = self.db.loads(row.pop("usage_json"))
        row["metadata"] = self.db.loads(row.pop("metadata_json"))
        return row

    def list(self, task_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = min(max(1, int(limit)), 1000)
        if task_id:
            rows = self.db.query("SELECT * FROM task_runs WHERE task_id=? ORDER BY created_at DESC LIMIT ?", (task_id, limit))
        else:
            rows = self.db.query("SELECT * FROM task_runs ORDER BY created_at DESC LIMIT ?", (limit,))
        out = []
        for row in rows:
            row["usage"] = self.db.loads(row.pop("usage_json"))
            row["metadata"] = self.db.loads(row.pop("metadata_json"))
            out.append(row)
        return out

    def update_metadata(self, run_id: str, patch: dict[str, Any]) -> dict:
        current = self.get(run_id)
        metadata = dict(current.get("metadata") or {})
        metadata.update(dict(patch or {}))
        self.db.execute(
            "UPDATE task_runs SET metadata_json=?,updated_at=? WHERE id=?",
            (self.db.dumps(metadata), time.time(), run_id),
        )
        return self.get(run_id)


    def acquire(self, run_id: str, owner: str, ttl_s: float = 60.0) -> dict:
        now = time.time()
        expires = now + max(5.0, float(ttl_s))
        with self.db.transaction() as conn:
            row = conn.execute("SELECT state,lease_owner,lease_expires FROM task_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            active_lease = row["lease_owner"] and row["lease_expires"] and float(row["lease_expires"]) > now
            if active_lease and row["lease_owner"] != owner:
                raise RuntimeError("run is leased by another worker")
            conn.execute(
                "UPDATE task_runs SET state='leased',lease_owner=?,lease_expires=?,updated_at=? WHERE id=?",
                (owner, expires, now, run_id),
            )
        self.bus.emit("run.leased", owner, {"run_id": run_id, "expires_at": expires})
        return self.get(run_id)

    def heartbeat(self, run_id: str, owner: str, ttl_s: float = 60.0) -> dict:
        now = time.time()
        expires = now + max(5.0, float(ttl_s))
        cur = self.db.execute(
            "UPDATE task_runs SET lease_expires=?,updated_at=? WHERE id=? AND lease_owner=?",
            (expires, now, run_id, owner),
        )
        if cur.rowcount != 1:
            raise RuntimeError("lease not held")
        return self.get(run_id)

    def set_state(self, run_id: str, state: str, actor: str = "system", **updates: Any) -> dict:
        if state not in RUN_STATES:
            raise ValueError(state)
        now = time.time()
        current = self.get(run_id)
        started = current["started_at"]
        finished = current["finished_at"]
        if state == "running" and started is None:
            started = now
        if state in ("succeeded", "failed", "cancelled"):
            finished = now
        usage = updates.get("usage", current["usage"])
        exit_code = updates.get("exit_code", current["exit_code"])
        self.db.execute(
            """UPDATE task_runs SET state=?,started_at=?,finished_at=?,exit_code=?,usage_json=?,updated_at=? WHERE id=?""",
            (state, started, finished, exit_code, self.db.dumps(usage), now, run_id),
        )
        self.bus.emit("run.state", actor, {"run_id": run_id, "from": current["state"], "to": state})
        return self.get(run_id)

    def release_expired(self, now: float | None = None) -> int:
        now = time.time() if now is None else float(now)
        cur = self.db.execute(
            """UPDATE task_runs SET state='queued',lease_owner=NULL,lease_expires=NULL,updated_at=?
               WHERE state='leased' AND lease_expires IS NOT NULL AND lease_expires<=?""",
            (now, now),
        )
        return int(cur.rowcount if cur.rowcount is not None else 0)
