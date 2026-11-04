from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import AgentState, AgentStatus


@dataclass(slots=True)
class EzerHTTPAdapter:
    """Thin adapter for E.O.P./EzerOS' existing FastAPI job API.

    The adapter intentionally has no FastAPI/httpx dependency.  Metatron only
    needs stdlib HTTP to control an already-running E.O.P. instance, which
    keeps its always-resident control plane small.  The same class is used for
    E.O.P. on the laptop and Ezra in the cloud.
    """

    id: str
    label: str
    kind: str
    base_url: str
    api_key: str | None = None
    remote: bool = False
    start_command: str = ""
    cwd: str | None = None
    startup_timeout_s: float = 8.0
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _health_cache: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _health_error: str | None = field(default=None, init=False, repr=False)
    _health_at: float = field(default=0.0, init=False, repr=False)
    _last_job_id: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: float = 3.0,
    ) -> Any:
        if not self.base_url:
            raise RuntimeError("EzerOS URL is not configured")
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1200]
            raise RuntimeError(f"EzerOS HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"EzerOS unreachable at {self.base_url}: {exc.reason}") from exc

    def _health(self, max_age_s: float = 2.0) -> dict[str, Any]:
        now = time.monotonic()
        if now - self._health_at <= max_age_s:
            if self._health_cache is not None:
                return self._health_cache
            if self._health_error:
                raise RuntimeError(self._health_error)
        try:
            data = self._request("GET", "/health", timeout=0.8)
            if not isinstance(data, dict):
                raise RuntimeError("invalid EzerOS health response")
        except Exception as exc:
            self._health_cache = None
            self._health_error = str(exc)[:500]
            self._health_at = now
            raise
        self._health_cache = data
        self._health_error = None
        self._health_at = now
        return data

    def detect(self) -> dict[str, Any]:
        if not self.base_url:
            return {"available": False, "url": "", "remote": self.remote}
        try:
            health = self._health()
            return {
                "available": True,
                "url": self.base_url,
                "remote": self.remote,
                "health": health.get("status", "unknown"),
            }
        except Exception as exc:
            return {
                "available": False,
                "url": self.base_url,
                "remote": self.remote,
                "reason": str(exc)[:300],
            }

    def status(self) -> AgentStatus:
        d = self.detect()
        if not d["available"]:
            state = AgentState.OFFLINE if self._proc is None else AgentState.ERROR
            return AgentStatus(self.id, self.label, self.kind, state, d.get("reason", "unreachable"))
        health = str(d.get("health", "unknown"))
        detail = f"API reachable · {health}"
        return AgentStatus(
            self.id, self.label, self.kind,
            AgentState.IDLE if health in {"ok", "degraded", "unknown"} else AgentState.ERROR,
            detail,
            pid=self._proc.pid if self._proc and self._proc.poll() is None else None,
            metrics={"remote": self.remote, "url": self.base_url},
        )

    def _launch_local(self) -> None:
        if self.remote or not self.start_command:
            return
        if self._proc is not None and self._proc.poll() is None:
            return
        argv = shlex.split(self.start_command, posix=(os.name != "nt"))
        if not argv:
            raise RuntimeError("E.O.P. start command is empty")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self._proc = subprocess.Popen(
            argv,
            cwd=self.cwd or None,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    def start(self) -> AgentStatus:
        if self.detect()["available"]:
            return self.status()
        if self.remote:
            return self.status()
        if not self.start_command:
            return AgentStatus(
                self.id, self.label, self.kind, AgentState.OFFLINE,
                "E.O.P. API is offline; configure METATRON_EOP_START_COMMAND to let Metatron start it",
            )
        try:
            self._launch_local()
        except Exception as exc:
            return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, str(exc)[:500])
        deadline = time.monotonic() + max(0.5, self.startup_timeout_s)
        while time.monotonic() < deadline:
            self._health_cache = None
            if self.detect()["available"]:
                return self.status()
            if self._proc is not None and self._proc.poll() is not None:
                return AgentStatus(
                    self.id, self.label, self.kind, AgentState.ERROR,
                    f"E.O.P. exited with code {self._proc.returncode}",
                )
            time.sleep(0.1)
        return AgentStatus(self.id, self.label, self.kind, AgentState.ERROR, "E.O.P. API did not become ready")

    def stop(self) -> AgentStatus:
        # Never terminate a service Metatron did not start itself.
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        self._proc = None
        self._health_cache = None
        self._health_error = None
        self._health_at = 0.0
        return self.status()

    @staticmethod
    def _task_payload(task: dict[str, Any]) -> dict[str, Any]:
        task_type = str(task.get("task_type") or "general")
        handler_name = str(task.get("handler_name") or "default")
        params = dict(task.get("params") or {})
        # Friendly Metatron task shape -> E.O.P. generic job parameters.
        for key in ("prompt", "project_dir", "memory_context", "provider", "model"):
            if key in task and key not in params:
                params[key] = task[key]
        if "prompt" not in params:
            prompt = task.get("description") or task.get("title")
            if prompt:
                params["prompt"] = str(prompt)
        return {"task_type": task_type, "handler_name": handler_name, "params": params}

    def submit(self, task: dict[str, Any]) -> dict[str, Any]:
        if not self.detect()["available"]:
            status = self.start()
            if status.state not in (AgentState.IDLE, AgentState.RUNNING):
                return {"accepted": False, "reason": status.detail}
        try:
            response = self._request("POST", "/jobs", self._task_payload(task), timeout=5.0) or {}
        except Exception as exc:
            return {"accepted": False, "reason": str(exc)[:800]}
        job = response.get("job") if isinstance(response, dict) else None
        if not isinstance(job, dict) or not job.get("id"):
            return {"accepted": False, "reason": "E.O.P. did not return a job id", "response": response}
        self._last_job_id = str(job["id"])
        return {"accepted": True, "job_id": self._last_job_id, "job": job, "transport": "http"}

    def job_status(self, job_id: str | None = None) -> dict[str, Any]:
        target = str(job_id or self._last_job_id or "")
        if not target:
            return {"available": False, "reason": "no E.O.P. job selected"}
        data = self._request("GET", f"/jobs/{urllib.parse.quote(target, safe='')}", timeout=3.0)
        return data if isinstance(data, dict) else {"raw": data}

    def cancel_job(self, job_id: str | None = None) -> dict[str, Any]:
        target = str(job_id or self._last_job_id or "")
        if not target:
            return {"cancelled": False, "reason": "no E.O.P. job selected"}
        data = self._request("POST", f"/jobs/{urllib.parse.quote(target, safe='')}/cancel", {}, timeout=3.0)
        return data if isinstance(data, dict) else {"cancelled": True, "job_id": target}

    def stats(self) -> dict[str, Any]:
        data = self._request("GET", "/stats", timeout=3.0)
        return data if isinstance(data, dict) else {"raw": data}

    def list_jobs(self, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        data = self._request("GET", f"/jobs?limit={limit}", timeout=3.0)
        return data if isinstance(data, dict) else {"jobs": [], "count": 0}


class HermesLocalAdapter(EzerHTTPAdapter):
    """E.O.P. / Hermes Local through the EzerOS HTTP control surface."""


class HermesCloudAdapter(EzerHTTPAdapter):
    """Ezra / Hermes Cloud through the same EzerOS API over the network."""
