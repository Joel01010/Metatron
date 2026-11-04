from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from .base import AgentState, AgentStatus


@dataclass(slots=True)
class ProcessAdapter:
    id: str
    label: str
    kind: str
    executable: str
    args: list[str] = field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] | None = None
    log_dir: str | None = None
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _log: BinaryIO | None = field(default=None, init=False, repr=False)
    _detect_cache: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _detect_at: float = field(default=0.0, init=False, repr=False)

    def detect(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._detect_cache is not None and now - self._detect_at < 10.0:
            return dict(self._detect_cache)
        exe = shutil.which(self.executable) or (self.executable if Path(self.executable).exists() else None)
        self._detect_cache = {"available": bool(exe), "path": exe}
        self._detect_at = now
        return dict(self._detect_cache)

    def status(self) -> AgentStatus:
        if self._proc is None:
            state, pid, detail = AgentState.OFFLINE, None, ""
        elif self._proc.poll() is None:
            state, pid, detail = AgentState.RUNNING, self._proc.pid, ""
        else:
            state = AgentState.ERROR if self._proc.returncode else AgentState.OFFLINE
            pid = self._proc.pid
            detail = f"exit={self._proc.returncode}"
        return AgentStatus(self.id, self.label, self.kind, state, detail=detail, pid=pid)

    def _open_log(self) -> BinaryIO | int:
        if not self.log_dir:
            return subprocess.DEVNULL
        path = Path(self.log_dir)
        path.mkdir(parents=True, exist_ok=True)
        log_path = path / f"{self.id}.log"
        # Keep agent output out of RAM and prevent persistent logs growing forever.
        if log_path.exists() and log_path.stat().st_size > 4 * 1024 * 1024:
            rotated = path / f"{self.id}.log.1"
            try:
                rotated.unlink(missing_ok=True)
                log_path.replace(rotated)
            except OSError:
                pass
        self._log = open(log_path, "ab", buffering=0)
        return self._log

    def start(self) -> AgentStatus:
        if self._proc is not None and self._proc.poll() is None:
            return self.status()
        detected = self.detect()
        if not detected["available"]:
            return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, "executable not found")
        merged_env = os.environ.copy()
        if self.env:
            merged_env.update(self.env)
        creationflags = 0
        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        log = self._open_log()
        self._proc = subprocess.Popen(
            [str(detected["path"]), *self.args],
            cwd=self.cwd,
            env=merged_env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        return self.status()

    def stop(self) -> AgentStatus:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        if self._log is not None:
            try:
                self._log.close()
            finally:
                self._log = None
        return self.status()

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        return {"accepted": False, "reason": "generic adapter has no task protocol", "task": task}
