from __future__ import annotations

import base64
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .base import AgentState, AgentStatus
from .process import ProcessAdapter


@dataclass(slots=True)
class OpenCodeAdapter(ProcessAdapter):
    """OpenCode headless HTTP adapter.

    Uses `opencode serve` and the documented /session endpoints. Metatron sends
    async prompts so its own JSONL control loop never blocks on a long agent run.
    """

    id: str = "opencode"
    label: str = "OpenCode"
    kind: str = "opencode"
    executable: str = "opencode"
    args: list[str] = None  # type: ignore
    host: str = "127.0.0.1"
    port: int = 4096
    username: str = "opencode"
    password: str | None = None

    def __post_init__(self):
        configured = os.environ.get("OPENCODE_SERVER_PASSWORD") or None
        self.password = self.password or configured or secrets.token_urlsafe(32)
        self.username = os.environ.get("OPENCODE_SERVER_USERNAME", self.username)
        if self.args is None:
            self.args = ["serve", "--hostname", "127.0.0.1", "--port", str(self.port)]
        self.host = "127.0.0.1"
        env = dict(self.env or {})
        env["OPENCODE_SERVER_PASSWORD"] = self.password
        env["OPENCODE_SERVER_USERNAME"] = self.username
        self.env = env

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.password:
            raw = f"{self.username}:{self.password}".encode("utf-8")
            headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
        return headers

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None, timeout: float = 3.0) -> Any:
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")[:1000]
            raise RuntimeError(f"OpenCode HTTP {exc.code}: {raw}") from exc

    def server_available(self) -> bool:
        try:
            self._request("GET", "/session/status", timeout=0.5)
            return True
        except Exception:
            return False

    def status(self) -> AgentStatus:
        own = ProcessAdapter.status(self)
        if own.state == AgentState.RUNNING:
            return own
        if self.server_available():
            return AgentStatus(self.id, self.label, self.kind, AgentState.IDLE, "headless server reachable")
        return own

    def start(self) -> AgentStatus:
        if self.server_available():
            return AgentStatus(self.id, self.label, self.kind, AgentState.IDLE, "using existing headless server")
        status = ProcessAdapter.start(self)
        if status.state == AgentState.ERROR:
            return status
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self.server_available():
                return self.status()
            time.sleep(0.1)
        ProcessAdapter.stop(self)
        return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, "server did not become ready")

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        if not self.server_available():
            status = self.start()
            if status.state == AgentState.ERROR:
                return {"accepted": False, "reason": status.detail}
        title = str(task.get("title") or "Metatron task")[:200]
        prompt = str(task.get("prompt") or task.get("description") or task.get("title") or "").strip()
        if not prompt:
            return {"accepted": False, "reason": "task has no prompt/description/title"}
        session = self._request("POST", "/session", {"title": title}, timeout=5.0) or {}
        session_id = session.get("id") or session.get("ID")
        if not session_id:
            return {"accepted": False, "reason": "OpenCode did not return a session id", "response": session}
        body: dict[str, Any] = {"parts": [{"type": "text", "text": prompt}]}
        if task.get("agent"):
            body["agent"] = task["agent"]
        if task.get("model"):
            body["model"] = task["model"]
        self._request("POST", f"/session/{session_id}/prompt_async", body, timeout=5.0)
        return {"accepted": True, "session_id": session_id, "mode": "async"}

    def abort(self, session_id: str) -> bool:
        result = self._request("POST", f"/session/{session_id}/abort", {}, timeout=5.0)
        return bool(result)
