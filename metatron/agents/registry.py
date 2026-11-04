from __future__ import annotations

from typing import Any

from .base import AgentAdapter


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, AgentAdapter] = {}

    def register(self, agent: AgentAdapter) -> None:
        if agent.id in self._agents:
            raise ValueError(f"duplicate agent id {agent.id}")
        self._agents[agent.id] = agent

    def get(self, agent_id: str) -> AgentAdapter:
        return self._agents[agent_id]

    def ids(self) -> tuple[str, ...]:
        return tuple(self._agents)

    def list(self, include_detect: bool = True) -> list[dict[str, Any]]:
        out = []
        for a in self._agents.values():
            status = a.status().to_dict()
            if include_detect:
                status["detect"] = a.detect()
            out.append(status)
        return out

    def stop_all(self) -> None:
        for agent in self._agents.values():
            try:
                agent.stop()
            except Exception:
                pass
