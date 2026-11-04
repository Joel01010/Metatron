from __future__ import annotations

import collections
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class JsonRpcError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass(slots=True)
class JsonRpcProcess:
    command: list[str]
    cwd: str | None = None
    env: dict[str, str] | None = None
    log_path: str | None = None
    event_limit: int = 500
    request_limit: int = 100
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _reader: threading.Thread | None = field(default=None, init=False, repr=False)
    _stderr: Any = field(default=None, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    _pending: dict[int, queue.Queue] = field(default_factory=dict, init=False, repr=False)
    _events: collections.deque = field(init=False, repr=False)
    _server_requests: collections.deque = field(init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._events = collections.deque(maxlen=max(10, self.event_limit))
        self._server_requests = collections.deque(maxlen=max(10, self.request_limit))

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self.running and self._proc is not None else None

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            merged = os.environ.copy()
            if self.env:
                merged.update(self.env)
            stderr: Any = subprocess.DEVNULL
            if self.log_path:
                p = Path(self.log_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                if p.exists() and p.stat().st_size > 4 * 1024 * 1024:
                    p1 = p.with_suffix(p.suffix + ".1")
                    try:
                        p1.unlink(missing_ok=True); p.replace(p1)
                    except OSError:
                        pass
                self._stderr = open(p, "ab", buffering=0)
                stderr = self._stderr
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            self._proc = subprocess.Popen(
                self.command, cwd=self.cwd, env=merged,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
                text=True, encoding="utf-8", bufsize=1, creationflags=flags,
            )
            self._reader = threading.Thread(target=self._read_loop, name="jsonrpc-reader", daemon=True)
            self._reader.start()

    def _read_loop(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                rid = obj.get("id")
                if rid is not None and ("result" in obj or "error" in obj):
                    with self._lock:
                        q = self._pending.get(int(rid)) if isinstance(rid, int) else None
                    if q is not None:
                        try: q.put_nowait(obj)
                        except queue.Full: pass
                    continue
                if rid is not None and "method" in obj:
                    self._server_requests.append(obj)
                    continue
                if "method" in obj:
                    self._events.append(obj)
        finally:
            with self._lock:
                for q in self._pending.values():
                    try: q.put_nowait({"error": {"code": -1, "message": "RPC process exited"}})
                    except queue.Full: pass

    def _write(self, payload: dict[str, Any]) -> None:
        if not self.running or self._proc is None or self._proc.stdin is None:
            raise JsonRpcError("RPC process is not running")
        try:
            self._proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            self._proc.stdin.flush()
        except Exception as exc:
            raise JsonRpcError(f"failed to write RPC request: {exc}") from exc

    def request(self, method: str, params: Any = None, timeout_s: float = 30.0) -> Any:
        self.start()
        with self._lock:
            rid = self._next_id; self._next_id += 1
            q: queue.Queue = queue.Queue(maxsize=1)
            self._pending[rid] = q
            payload: dict[str, Any] = {"id": rid, "method": method}
            if params is not None:
                payload["params"] = params
            self._write(payload)
        try:
            obj = q.get(timeout=timeout_s)
        except queue.Empty as exc:
            raise JsonRpcError(f"RPC timeout: {method}") from exc
        finally:
            with self._lock:
                self._pending.pop(rid, None)
        if "error" in obj:
            err = obj.get("error") or {}
            raise JsonRpcError(str(err.get("message") or "RPC error"), err.get("code"), err.get("data"))
        return obj.get("result")

    def notify(self, method: str, params: Any = None) -> None:
        self.start()
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        with self._lock:
            self._write(payload)

    def respond(self, request_id: int | str, result: Any = None, error: dict[str, Any] | None = None) -> None:
        payload: dict[str, Any] = {"id": request_id}
        if error is not None:
            payload["error"] = error
        else:
            payload["result"] = result
        with self._lock:
            self._write(payload)

    def events(self, clear: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            out = list(self._events)
            if clear: self._events.clear()
        return out

    def server_requests(self, clear: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            out = list(self._server_requests)
            if clear: self._server_requests.clear()
        return out

    def stop(self) -> None:
        with self._lock:
            proc = self._proc; self._proc = None
        if proc is not None:
            if proc.poll() is None:
                try:
                    if proc.stdin is not None: proc.stdin.close()
                except Exception: pass
                proc.terminate()
                try: proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(timeout=2)
            for pipe in (proc.stdout, proc.stdin):
                try:
                    if pipe is not None and not pipe.closed: pipe.close()
                except Exception: pass
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(timeout=1)
        self._reader = None
        if self._stderr is not None:
            try: self._stderr.close()
            finally: self._stderr = None
