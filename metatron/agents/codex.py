from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AgentState, AgentStatus
from ..jsonrpc import JsonRpcProcess, JsonRpcError


@dataclass(slots=True)
class CodexAdapter:
    """Codex app-server adapter using the documented stdio JSON-RPC protocol."""

    id: str = "codex"
    label: str = "Codex"
    kind: str = "codex"
    executable: str = "codex"
    cwd: str | None = None
    log_dir: str | None = None
    _rpc: JsonRpcProcess | None = field(default=None, init=False, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)

    _detect_at: float = field(default=-1.0, init=False, repr=False)
    _detect_exe: str = field(default="", init=False, repr=False)
    _detect_key: str = field(default="", init=False, repr=False)

    def detect(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._detect_at < 0 or now - self._detect_at >= 10.0 or self._detect_key != self.executable:
            self._detect_exe = shutil.which(self.executable) or (self.executable if Path(self.executable).exists() else "")
            self._detect_at = now
            self._detect_key = self.executable
        exe = self._detect_exe or None
        return {"available": bool(exe), "path": exe, "transport": "app-server-stdio"}

    def status(self) -> AgentStatus:
        if self._rpc is not None and self._rpc.running:
            return AgentStatus(self.id, self.label, self.kind, AgentState.IDLE if self._initialized else AgentState.RUNNING,
                               "app-server ready" if self._initialized else "initializing", pid=self._rpc.pid)
        return AgentStatus(self.id, self.label, self.kind, AgentState.OFFLINE)

    def start(self) -> AgentStatus:
        if self._rpc is not None and self._rpc.running and self._initialized:
            return self.status()
        d = self.detect()
        if not d["available"]:
            return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, "codex executable not found")
        log = str(Path(self.log_dir) / "codex-app-server.log") if self.log_dir else None
        self._rpc = JsonRpcProcess([str(d["path"]), "app-server", "--listen", "stdio://"], cwd=self.cwd, log_path=log)
        try:
            self._rpc.start()
            self._rpc.request("initialize", {
                "clientInfo": {"name": "metatron", "title": "Metatron", "version": "0.2.0"}
            }, timeout_s=15)
            self._rpc.notify("initialized")
            self._initialized = True
        except Exception as exc:
            self.stop()
            return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, f"app-server init failed: {exc}")
        return self.status()

    def stop(self) -> AgentStatus:
        if self._rpc is not None:
            self._rpc.stop()
        self._rpc = None
        self._initialized = False
        return self.status()

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        status = self.start()
        if status.state == AgentState.ERROR or self._rpc is None:
            return {"accepted": False, "reason": status.detail}
        prompt = str(task.get("prompt") or task.get("description") or task.get("title") or "").strip()
        if not prompt:
            return {"accepted": False, "reason": "task has no prompt/description/title"}
        cwd = str(task.get("cwd") or self.cwd or "").strip()
        thread_params: dict[str, Any] = {}
        if cwd: thread_params["cwd"] = cwd
        if task.get("model"): thread_params["model"] = task["model"]
        try:
            thread_result = self._rpc.request("thread/start", thread_params, timeout_s=30) or {}
            thread = thread_result.get("thread") or {}
            thread_id = thread.get("id") or thread_result.get("threadId")
            if not thread_id:
                return {"accepted": False, "reason": "thread/start returned no thread id", "response": thread_result}
            turn_params: dict[str, Any] = {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
            }
            turn_result = self._rpc.request("turn/start", turn_params, timeout_s=30) or {}
            turn = turn_result.get("turn") or {}
            return {
                "accepted": True,
                "thread_id": thread_id,
                "turn_id": turn.get("id") or turn_result.get("turnId"),
                "mode": "streaming",
            }
        except JsonRpcError as exc:
            return {"accepted": False, "reason": str(exc), "code": exc.code, "data": exc.data}

    def events(self, clear: bool = False) -> list[dict[str, Any]]:
        return [] if self._rpc is None else self._rpc.events(clear)

    def pending_requests(self, clear: bool = False) -> list[dict[str, Any]]:
        return [] if self._rpc is None else self._rpc.server_requests(clear)

    def respond(self, request_id: int | str, result: Any) -> None:
        if self._rpc is None:
            raise RuntimeError("Codex app-server is not running")
        self._rpc.respond(request_id, result=result)

    def interrupt(self, thread_id: str, turn_id: str | None = None) -> Any:
        if self._rpc is None:
            raise RuntimeError("Codex app-server is not running")
        params: dict[str, Any] = {"threadId": thread_id}
        if turn_id: params["turnId"] = turn_id
        return self._rpc.request("turn/interrupt", params, timeout_s=10)
