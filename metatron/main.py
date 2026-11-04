from __future__ import annotations

import json
import queue
import sys
import threading
import time
from typing import Any

from .core import Metatron
from .events import Event
from .server import Dispatcher, ProtocolError
from .schema import SchemaError, validate_protocol_request


class StdoutBridge:
    """Demultiplex-friendly stdout writer with bounded push-event transport.

    Control events are ordered and lossless under normal operation. High-rate
    ephemeral level events are coalesced latest-wins and emitted at <=30 Hz only
    while a renderer explicitly subscribes.
    """

    def __init__(self, app: Metatron, max_control_events: int = 4096) -> None:
        self.app = app
        self._write_lock = threading.RLock()
        self._control: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max_control_events)
        self._latest: dict[str, dict[str, Any]] = {}
        self._latest_lock = threading.RLock()
        self._live_consumers: set[str] = set()
        self._stop = threading.Event()
        self._unsubscribe = app.bus.subscribe(self._on_event)
        self._thread = threading.Thread(target=self._pump, name="metatron-stdout-events", daemon=True)
        self._thread.start()

    @staticmethod
    def _is_coalesced(topic: str, persisted: bool) -> bool:
        return (not persisted) and (
            topic.endswith(".level") or topic in {"speech.runtime.event", "presence.frame"}
        )

    def _on_event(self, ev: Event) -> None:
        payload = {
            "live_seq": ev.live_seq,
            "seq": ev.seq,
            "topic": ev.topic,
            "source": ev.source,
            "payload": ev.payload,
            "persisted": ev.persisted,
        }
        if self._is_coalesced(ev.topic, ev.persisted):
            if not self._live_consumers:
                return
            with self._latest_lock:
                self._latest[ev.topic] = payload
            return
        # Do not silently drop control/state events. Backpressure here is
        # intentional and bounded; pathological UI failure cannot allocate RAM
        # without limit.
        self._control.put(payload)

    def set_live(self, enabled: bool, consumer: str = "default") -> dict[str, Any]:
        consumer = str(consumer or "default")[:64]
        if enabled:
            self._live_consumers.add(consumer)
        else:
            self._live_consumers.discard(consumer)
        if not self._live_consumers:
            with self._latest_lock:
                self._latest.clear()
        return {
            "enabled": bool(self._live_consumers), "consumers": sorted(self._live_consumers),
            "max_hz": 30, "coalescing": "latest-wins",
        }

    def write(self, obj: dict[str, Any]) -> None:
        raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
        with self._write_lock:
            sys.stdout.write(raw + "\n")
            sys.stdout.flush()

    def _pump(self) -> None:
        frame_s = 1.0 / 30.0
        next_frame = time.monotonic()
        while not self._stop.is_set():
            # Drain ordered control events first.
            try:
                item = self._control.get(timeout=0.01)
                if item is None:
                    break
                self.write({"method": "metatron.event", "params": item})
                while True:
                    item = self._control.get_nowait()
                    if item is None:
                        return
                    self.write({"method": "metatron.event", "params": item})
            except queue.Empty:
                pass

            now = time.monotonic()
            if self._live_consumers and now >= next_frame:
                with self._latest_lock:
                    pending = list(self._latest.values())
                    self._latest.clear()
                for payload in pending:
                    self.write({"method": "metatron.event", "params": payload})
                next_frame = now + frame_s

    def close(self) -> None:
        self._unsubscribe()
        self._stop.set()
        try:
            self._control.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=1.0)


def main() -> int:
    app = Metatron()
    dispatcher = Dispatcher(app)
    bridge = StdoutBridge(app)
    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            rid = None
            try:
                req = json.loads(raw)
                # Preserve a syntactically valid request id even when another
                # envelope field fails validation, so clients can correlate
                # invalid_request responses instead of timing out.
                if isinstance(req, dict):
                    candidate_id = req.get("id")
                    if isinstance(candidate_id, (int, str)) and not isinstance(candidate_id, bool):
                        rid = candidate_id
                rid, cmd, params = validate_protocol_request(req)
                if cmd == "bridge.live_events":
                    result = bridge.set_live(bool(params.get("enabled", False)), str(params.get("consumer") or "default"))
                else:
                    result = dispatcher.dispatch(cmd, params)
                out = {"id": rid, "ok": True, "result": result}
            except SchemaError as e:
                out = {"id": rid, "ok": False, "error": {"code": "invalid_request", "message": str(e)}}
            except ProtocolError as e:
                out = {"id": rid, "ok": False, "error": {"code": e.code, "message": str(e)}}
            except Exception as e:
                out = {"id": rid, "ok": False, "error": {"code": "internal", "message": str(e)}}
            bridge.write(out)
    finally:
        bridge.close()
        app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
