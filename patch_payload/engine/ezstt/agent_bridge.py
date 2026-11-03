"""Tiny optional assistant bridge for the unified EZSTT/OpenDex fork.

Memory goals:
- zero third-party dependencies
- disabled by default
- bounded text history
- talks to an already-running OpenAI-compatible HTTP endpoint
- never loads an LLM into the EZSTT process
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
import urllib.request
import urllib.error


@dataclass
class AgentConfig:
    enabled: bool = False
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = ""
    api_key: str = ""
    max_history_messages: int = 12
    max_tokens: int = 384
    system_prompt: str = (
        "You are a concise voice-first desktop assistant. "
        "Answer clearly and briefly. Avoid markdown unless the user asks for it."
    )


def load_agent_config(path: Path) -> AgentConfig:
    cfg = AgentConfig()
    if not path.exists():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return cfg

    for key in (
        "enabled",
        "base_url",
        "model",
        "api_key",
        "max_history_messages",
        "max_tokens",
        "system_prompt",
    ):
        if key in raw:
            setattr(cfg, key, raw[key])

    cfg.max_history_messages = max(2, min(int(cfg.max_history_messages), 40))
    cfg.max_tokens = max(64, min(int(cfg.max_tokens), 2048))
    return cfg


class AgentBridge:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        self.cfg = load_agent_config(self.config_path)
        self.history = deque(maxlen=self.cfg.max_history_messages)

    def status(self) -> dict:
        return {
            "enabled": bool(self.cfg.enabled and self.cfg.model),
            "base_url": self.cfg.base_url,
            "model": self.cfg.model,
            "history_messages": len(self.history),
            "max_history_messages": self.cfg.max_history_messages,
        }

    def clear(self) -> None:
        with self._lock:
            self.history.clear()

    def chat(self, text: str) -> str:
        text = str(text or "").strip()
        if not text:
            raise ValueError("empty assistant message")
        if not self.cfg.enabled:
            raise RuntimeError("assistant is disabled")
        if not self.cfg.model:
            raise RuntimeError("assistant model is not configured")

        with self._lock:
            messages = [{"role": "system", "content": self.cfg.system_prompt}]
            messages.extend(self.history)
            messages.append({"role": "user", "content": text})

            body = json.dumps(
                {
                    "model": self.cfg.model,
                    "messages": messages,
                    "max_tokens": self.cfg.max_tokens,
                    "temperature": 0.2,
                    "stream": False,
                }
            ).encode("utf-8")

            url = self.cfg.base_url.rstrip("/") + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Unified-NPU-Jarvis/1",
            }
            if self.cfg.api_key:
                headers["Authorization"] = "Bearer " + self.cfg.api_key

            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from e
            except Exception as e:
                raise RuntimeError(f"LLM request failed: {e}") from e

            try:
                answer = payload["choices"][0]["message"]["content"].strip()
            except Exception as e:
                raise RuntimeError("LLM response did not contain choices[0].message.content") from e

            self.history.append({"role": "user", "content": text})
            self.history.append({"role": "assistant", "content": answer})
            return answer
