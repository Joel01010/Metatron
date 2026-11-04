from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Protocol


class AgentState(str, Enum):
    OFFLINE = "offline"
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"


@dataclass(slots=True)
class AgentStatus:
    id: str
    label: str
    kind: str
    state: AgentState
    detail: str = ""
    pid: int | None = None
    metrics: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d


class AgentAdapter(Protocol):
    id: str
    label: str
    kind: str

    def detect(self) -> dict[str, Any]: ...
    def status(self) -> AgentStatus: ...
    def start(self) -> AgentStatus: ...
    def stop(self) -> AgentStatus: ...
    def submit(self, task: dict[str, Any]) -> dict[str, Any]: ...
