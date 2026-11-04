from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AgentState, AgentStatus
from ..env import child_environment
from ..job import owned_job


@dataclass(slots=True)
class ClaudeCodeAdapter:
    """Transient Claude Code headless adapter.

    `start()` only verifies readiness. `submit()` launches a bounded `claude -p`
    job and returns immediately; no resident Claude process exists while idle.
    """

    id: str = "claude-code"
    label: str = "Claude Code"
    kind: str = "claude-code"
    executable: str = "claude"
    cwd: str | None = None
    env: dict[str, str] | None = None
    log_dir: str | None = None
    transient: bool = True
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _result_path: Path | None = field(default=None, init=False, repr=False)
    _stderr_path: Path | None = field(default=None, init=False, repr=False)
    _last_result: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _job: object | None = field(default=None, init=False, repr=False)

    def detect(self) -> dict[str, Any]:
        exe = shutil.which(self.executable) or (self.executable if Path(self.executable).exists() else None)
        return {"available": bool(exe), "path": exe, "transport": "headless-print"}

    def status(self) -> AgentStatus:
        if self._proc is not None and self._proc.poll() is None:
            return AgentStatus(self.id, self.label, self.kind, AgentState.RUNNING, "headless task running", pid=self._proc.pid)
        d = self.detect()
        return AgentStatus(
            self.id, self.label, self.kind,
            AgentState.IDLE if d["available"] else AgentState.OFFLINE,
            "ready (transient)" if d["available"] else "executable not found",
        )

    def start(self) -> AgentStatus:
        d = self.detect()
        if not d["available"]:
            return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, "claude executable not found")
        return self.status()

    def build_command(self, task: dict[str, Any]) -> list[str]:
        d = self.detect()
        if not d["available"]:
            raise RuntimeError("claude executable not found")
        prompt = str(task.get("prompt") or task.get("description") or task.get("title") or "").strip()
        if not prompt:
            raise ValueError("task has no prompt/description/title")
        max_turns = min(max(1, int(task.get("max_turns", 8))), 50)
        cmd = [str(d["path"]), "-p", prompt, "--output-format", "json", "--max-turns", str(max_turns)]
        if task.get("session_id"):
            cmd += ["--resume", str(task["session_id"])]
        if task.get("model"):
            cmd += ["--model", str(task["model"])]
        if task.get("permission_mode"):
            cmd += ["--permission-mode", str(task["permission_mode"])]
        return cmd

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        if self._proc is not None and self._proc.poll() is None:
            return {"accepted": False, "reason": "Claude Code already has a running local task"}
        try:
            cmd = self.build_command(task)
        except Exception as exc:
            return {"accepted": False, "reason": str(exc)}
        log_dir = Path(self.log_dir or (Path.home() / ".metatron" / "logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        self._result_path = log_dir / "claude-code-result.json"
        self._stderr_path = log_dir / "claude-code-stderr.log"
        self._last_result = None
        out = open(self._result_path, "wb")
        err = open(self._stderr_path, "wb")
        merged = child_environment(extra=self.env or {})
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                cmd, cwd=str(task.get("cwd") or self.cwd) if (task.get("cwd") or self.cwd) else None,
                env=merged, stdin=subprocess.DEVNULL, stdout=out, stderr=err, creationflags=flags,
            )
            self._job = owned_job("Metatron-claude")
            self._job.assign_pid(self._proc.pid)
        finally:
            # Popen duplicates/owns child handles; parent does not retain them.
            out.close(); err.close()
        return {"accepted": True, "pid": self._proc.pid, "mode": "headless", "result_path": str(self._result_path)}

    def result(self) -> dict[str, Any] | None:
        if self._proc is None or self._proc.poll() is None:
            return None
        if self._last_result is not None:
            return self._last_result
        if self._result_path is None or not self._result_path.exists():
            return {"ok": False, "exit_code": self._proc.returncode, "error": "result file missing"}
        if self._result_path.stat().st_size > 16 * 1024 * 1024:
            self._last_result = {"ok": False, "exit_code": self._proc.returncode, "error": "result exceeded 16 MiB safety cap"}
            return self._last_result
        try:
            payload = json.loads(self._result_path.read_text(encoding="utf-8") or "{}")
            self._last_result = {"ok": self._proc.returncode == 0 and not bool(payload.get("is_error")), "exit_code": self._proc.returncode, **payload}
        except Exception as exc:
            self._last_result = {"ok": False, "exit_code": self._proc.returncode, "error": f"invalid Claude JSON: {exc}"}
        return self._last_result

    def stop(self) -> AgentStatus:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try: self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill(); self._proc.wait(timeout=2)
        if self._job is not None:
            self._job.close(); self._job = None
        return self.status()
