from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .env import child_environment
from .job import owned_job
from typing import Any

from .memory import ModelBroker


class WorkerError(RuntimeError):
    pass


@dataclass(slots=True)
class JsonlWorkerSupervisor:
    """Lazy child-process supervisor for heavy runtimes.

    The Metatron core stays free of OpenVINO/ML imports. A worker is admitted
    through ModelBroker, spawned on first request, spoken to over JSON-lines,
    and can be killed after idle to reclaim its entire runtime heap.
    """

    name: str
    command: list[str]
    broker: ModelBroker
    cwd: str | None = None
    env: dict[str, str] | None = None
    log_path: str | None = None
    request_timeout_s: float = 30.0
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _job: object | None = field(default=None, init=False, repr=False)
    _reader: threading.Thread | None = field(default=None, init=False, repr=False)
    _stderr: Any = field(default=None, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    _pending: dict[int, queue.Queue] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _last_used: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        # Broker eviction/idle sweep must terminate the real worker process.
        self.broker.set_unload_callback(self.name, self._terminate_process)

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
            self.broker.load(self.name)
            merged = child_environment(extra=self.env or {})
            stderr: Any = subprocess.DEVNULL
            if self.log_path:
                p = Path(self.log_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                if p.exists() and p.stat().st_size > 4 * 1024 * 1024:
                    p1 = p.with_suffix(p.suffix + ".1")
                    try:
                        p1.unlink(missing_ok=True)
                        p.replace(p1)
                    except OSError:
                        pass
                self._stderr = open(p, "ab", buffering=0)
                stderr = self._stderr
            creationflags = 0
            if os.name == "nt":
                creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self._proc = subprocess.Popen(
                    self.command,
                    cwd=self.cwd,
                    env=merged,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=stderr,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                    creationflags=creationflags,
                )
                self._job = owned_job(f"Metatron-worker-{self.name}")
                self._job.assign_pid(self._proc.pid)
            except Exception:
                self.broker.unload(self.name)
                if self._stderr is not None:
                    self._stderr.close(); self._stderr = None
                raise
            self._last_used = time.monotonic()
            self._reader = threading.Thread(target=self._read_loop, name=f"worker-{self.name}", daemon=True)
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
                    rid = obj.get("id")
                    if isinstance(rid, int):
                        with self._lock:
                            q = self._pending.get(rid)
                        if q is not None:
                            try:
                                q.put_nowait(obj)
                            except queue.Full:
                                pass
                except Exception:
                    # Protocol garbage is ignored; never accumulate raw output.
                    continue
        finally:
            with self._lock:
                for q in self._pending.values():
                    try:
                        q.put_nowait({"ok": False, "error": {"message": "worker exited"}})
                    except queue.Full:
                        pass

    def request(self, cmd: str, params: dict[str, Any] | None = None, timeout_s: float | None = None) -> Any:
        self.start()
        with self._lock:
            if not self.running or self._proc is None or self._proc.stdin is None:
                raise WorkerError(f"{self.name} is not running")
            rid = self._next_id
            self._next_id += 1
            q: queue.Queue = queue.Queue(maxsize=1)
            self._pending[rid] = q
            payload = {"id": rid, "cmd": cmd, "params": params or {}}
            try:
                self._proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
                self._proc.stdin.flush()
            except Exception as exc:
                self._pending.pop(rid, None)
                raise WorkerError(f"failed to write to {self.name}: {exc}") from exc
            self._last_used = time.monotonic()
            self.broker.touch(self.name)
        try:
            response = q.get(timeout=self.request_timeout_s if timeout_s is None else timeout_s)
        except queue.Empty as exc:
            raise WorkerError(f"{self.name} request timed out") from exc
        finally:
            with self._lock:
                self._pending.pop(rid, None)
        if not response.get("ok", False):
            err = response.get("error") or {}
            raise WorkerError(str(err.get("message") or "worker request failed"))
        return response.get("result")

    def _terminate_process(self) -> None:
        """Kill worker/close pipes without re-entering ModelBroker.unload()."""
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is not None:
            if proc.poll() is None:
                try:
                    if proc.stdin is not None:
                        proc.stdin.close()
                except Exception:
                    pass
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except Exception:
                pass
            try:
                if proc.stdin is not None and not proc.stdin.closed:
                    proc.stdin.close()
            except Exception:
                pass
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(timeout=1)
        self._reader = None
        if self._job is not None:
            self._job.close(); self._job = None
        if self._stderr is not None:
            try:
                self._stderr.close()
            finally:
                self._stderr = None

    def stop(self) -> None:
        # The broker invokes _terminate_process through its registered hook.
        self.broker.unload(self.name)

    def idle_for_s(self) -> float:
        return max(0.0, time.monotonic() - self._last_used) if self._last_used else float("inf")
