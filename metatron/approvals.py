from __future__ import annotations

import time
import uuid
from typing import Any

from .db import Database
from .events import EventBus


class ApprovalStore:
    def __init__(self, db: Database, bus: EventBus):
        self.db = db
        self.bus = bus

    def request(self, action: str, actor: str, payload: dict[str, Any], ttl_s: float | None = 600) -> dict:
        aid = str(uuid.uuid4())
        now = time.time()
        expires = now + ttl_s if ttl_s else None
        self.db.execute(
            "INSERT INTO approvals(id,action,actor,payload_json,status,expires_at,created_at) VALUES(?,?,?,?,?,?,?)",
            (aid, action, actor, self.db.dumps(payload), "pending", expires, now),
        )
        self.bus.emit("approval.requested", actor, {"approval_id": aid, "action": action})
        return self.get(aid)

    def get(self, approval_id: str) -> dict:
        rows = self.db.query("SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not rows:
            raise KeyError(approval_id)
        r = rows[0]
        r["payload"] = self.db.loads(r.pop("payload_json"))
        return r

    def list(self, status: str | None = None, limit: int = 100) -> list[dict]:
        limit = min(max(1, int(limit)), 1000)
        if status:
            rows = self.db.query("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit))
        else:
            rows = self.db.query("SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (limit,))
        for r in rows:
            r["payload"] = self.db.loads(r.pop("payload_json"))
        return rows

    def count_pending(self) -> int:
        rows = self.db.query("SELECT COUNT(*) AS n FROM approvals WHERE status='pending'")
        return int(rows[0]["n"]) if rows else 0

    def decide(self, approval_id: str, approved: bool, actor: str = "user") -> dict:
        current = self.get(approval_id)
        if current["status"] != "pending":
            return current
        status = "approved" if approved else "denied"
        self.db.execute("UPDATE approvals SET status=?,decided_at=? WHERE id=?", (status, time.time(), approval_id))
        self.bus.emit("approval.decided", actor, {"approval_id": approval_id, "status": status})
        return self.get(approval_id)

    def expire(self, now: float | None = None) -> int:
        now = time.time() if now is None else float(now)
        cur = self.db.execute(
            "UPDATE approvals SET status='expired',decided_at=? WHERE status='pending' AND expires_at IS NOT NULL AND expires_at<=?",
            (now, now),
        )
        return int(cur.rowcount if cur.rowcount is not None else 0)
