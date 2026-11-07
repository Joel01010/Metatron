from __future__ import annotations

import math
import time
import uuid
from typing import Any

from .db import Database
from .events import EventBus


class Scheduler:
    """Persistence-first interval scheduler with drift-free catch-up.

    Missed intervals collapse into one due event; Metatron does not stampede
    several old runs after sleep/resume.
    """

    def __init__(self, db: Database, bus: EventBus):
        self.db = db
        self.bus = bus

    def create_interval(self, label: str, task_template: dict[str, Any], interval_s: float,
                        agent_id: str | None = None, first_run: float | None = None) -> dict:
        if interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        sid = str(uuid.uuid4())
        now = time.time()
        next_run = first_run if first_run is not None else now + interval_s
        self.db.execute(
            """INSERT INTO schedules(id,label,agent_id,task_template_json,interval_s,next_run,enabled,created_at,updated_at)
               VALUES(?,?,?,?,?,?,1,?,?)""",
            (sid, label, agent_id, self.db.dumps(task_template), interval_s, next_run, now, now),
        )
        return self.get(sid)

    def get(self, schedule_id: str) -> dict:
        rows = self.db.query("SELECT * FROM schedules WHERE id=?", (schedule_id,))
        if not rows:
            raise KeyError(schedule_id)
        r = rows[0]
        r["task_template"] = self.db.loads(r.pop("task_template_json"))
        return r

    def list(self, enabled_only: bool = False) -> list[dict]:
        sql = "SELECT * FROM schedules" + (" WHERE enabled=1" if enabled_only else "") + " ORDER BY next_run"
        rows = self.db.query(sql)
        out = []
        for r in rows:
            r["task_template"] = self.db.loads(r.pop("task_template_json"))
            out.append(r)
        return out

    def set_enabled(self, schedule_id: str, enabled: bool) -> dict:
        self.get(schedule_id)
        now = time.time()
        self.db.execute("UPDATE schedules SET enabled=?,updated_at=? WHERE id=?", (1 if enabled else 0, now, schedule_id))
        self.bus.emit("schedule.updated", "user", {"schedule_id": schedule_id, "enabled": bool(enabled)})
        return self.get(schedule_id)

    def delete(self, schedule_id: str) -> bool:
        self.get(schedule_id)
        cur = self.db.execute("DELETE FROM schedules WHERE id=?", (schedule_id,))
        deleted = bool(cur.rowcount)
        if deleted:
            self.bus.emit("schedule.deleted", "user", {"schedule_id": schedule_id})
        return deleted


    def due(self, now: float | None = None) -> list[dict]:
        now = time.time() if now is None else float(now)
        rows = self.db.query("SELECT * FROM schedules WHERE enabled=1 AND next_run<=? ORDER BY next_run", (now,))
        due: list[dict] = []
        for r in rows:
            item = dict(r)
            item["task_template"] = self.db.loads(item.pop("task_template_json"))
            interval = float(item["interval_s"] or 0)
            if interval <= 0:
                self.db.execute("UPDATE schedules SET enabled=0,updated_at=? WHERE id=?", (now, item["id"]))
                continue
            # Advance from the old schedule boundary, not from now, but collapse
            # all missed ticks into one run after wake/resume.
            missed = max(1, math.floor((now - float(item["next_run"])) / interval) + 1)
            new_next = float(item["next_run"]) + missed * interval
            self.db.execute("UPDATE schedules SET next_run=?,updated_at=? WHERE id=?", (new_next, now, item["id"]))
            item["missed_intervals"] = missed - 1
            due.append(item)
            self.bus.emit("schedule.due", "scheduler", {
                "schedule_id": item["id"], "agent_id": item["agent_id"], "missed_intervals": missed - 1
            })
        return due
