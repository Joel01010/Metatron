from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from .db import Database


@dataclass(frozen=True, slots=True)
class Event:
    seq: int
    topic: str
    source: str
    payload: dict[str, Any]
    persisted: bool = True
    live_seq: int = 0


class EventBus:
    """Small synchronous event bus with persistent + ephemeral lanes.

    Normal control-plane events are written to SQLite and also mirrored into a
    bounded in-memory live ring. High-frequency audio/presence events use the
    ephemeral lane: they never hit SQLite, so 30-60 Hz amplitude updates cannot
    turn an always-on desktop assistant into a disk-write machine.
    """

    def __init__(self, db: Database, live_capacity: int = 1024):
        self.db = db
        self._subs: list[Callable[[Event], None]] = []
        self._lock = threading.RLock()
        self._live: deque[dict[str, Any]] = deque(maxlen=max(128, int(live_capacity)))
        self._live_seq = 0

    def subscribe(self, fn: Callable[[Event], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)
        return unsubscribe

    def _publish_live(self, *, topic: str, source: str, payload: dict[str, Any], persisted_seq: int, persisted: bool) -> int:
        with self._lock:
            self._live_seq += 1
            live_seq = self._live_seq
            self._live.append({
                "live_seq": live_seq,
                "seq": persisted_seq,
                "topic": topic,
                "source": source,
                "payload": payload,
                "persisted": persisted,
            })
        return live_seq

    def _notify(self, ev: Event) -> None:
        with self._lock:
            subs = tuple(self._subs)
        for fn in subs:
            try:
                fn(ev)
            except Exception:
                # Event observers must never be able to crash the control plane.
                pass

    def emit(self, topic: str, source: str, payload: dict[str, Any], *, persist: bool = True) -> Event:
        seq = self.db.append_event(topic, source, payload) if persist else 0
        live_seq = self._publish_live(
            topic=topic, source=source, payload=payload,
            persisted_seq=seq, persisted=persist,
        )
        ev = Event(seq=seq, topic=topic, source=source, payload=payload, persisted=persist, live_seq=live_seq)
        self._notify(ev)
        return ev

    def emit_ephemeral(self, topic: str, source: str, payload: dict[str, Any]) -> Event:
        return self.emit(topic, source, payload, persist=False)

    def tail(self, after_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        limit = min(max(1, int(limit)), 1000)
        rows = self.db.query(
            "SELECT seq,ts,topic,source,payload_json FROM events WHERE seq>? ORDER BY seq LIMIT ?",
            (int(after_seq), limit),
        )
        for row in rows:
            row["payload"] = self.db.loads(row.pop("payload_json"))
        return rows

    def live_tail(self, after_live_seq: int = 0, limit: int = 256) -> list[dict[str, Any]]:
        """Return bounded recent live events, including ephemeral audio levels.

        This is intentionally memory-only. A future Tauri host can replace
        polling with a direct subscription without changing event semantics.
        """
        limit = min(max(1, int(limit)), 1024)
        with self._lock:
            rows = [dict(x) for x in self._live if int(x["live_seq"]) > int(after_live_seq)]
        return rows[:limit]
