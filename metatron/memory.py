from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class Reservation:
    name: str
    estimated_mib: int
    evictable: bool = True
    loaded: bool = False
    last_used: float = 0.0
    unload: Callable[[], None] | None = None
    priority: int = 50
    idle_unload_s: float | None = None
    exclusive_group: str | None = None
    measured_mib: float | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def charge_mib(self) -> int:
        if self.measured_mib is None:
            return int(self.estimated_mib)
        # Keep a 10% safety cushion on measured working set.
        return max(1, int(max(self.estimated_mib * 0.75, self.measured_mib * 1.10)))


class MemoryBudgetError(RuntimeError):
    pass


class ModelBroker:
    """Admission controller for optional heavyweight resources.

    It plans before loading, evicts low-priority/LRU resources, enforces
    mutual-exclusion groups, learns from measured RSS, and supports idle sweeps.
    """

    def __init__(self, hard_limit_mib: int, fixed_mib: int = 0, headroom_mib: int = 0):
        self.hard_limit_mib = int(hard_limit_mib)
        self.fixed_mib = int(fixed_mib)
        self.headroom_mib = int(headroom_mib)
        self._items: dict[str, Reservation] = {}
        self._lock = threading.RLock()

    @property
    def usable_mib(self) -> int:
        return max(0, self.hard_limit_mib - self.fixed_mib - self.headroom_mib)

    @property
    def used_mib(self) -> int:
        with self._lock:
            return sum(x.charge_mib for x in self._items.values() if x.loaded)

    def register(self, item: Reservation) -> None:
        if item.estimated_mib <= 0:
            raise ValueError("reservation must be positive")
        with self._lock:
            self._items[item.name] = item

    def set_estimated_mib(self, name: str, estimated_mib: int) -> None:
        value = int(estimated_mib)
        if value <= 0:
            raise ValueError("estimated MiB must be positive")
        with self._lock:
            if name not in self._items:
                raise KeyError(name)
            self._items[name].estimated_mib = value

    def set_measured_mib(self, name: str, measured_mib: float | None) -> None:
        with self._lock:
            if name not in self._items:
                raise KeyError(name)
            self._items[name].measured_mib = None if measured_mib is None else max(0.0, float(measured_mib))

    def set_unload_callback(self, name: str, callback: Callable[[], None] | None) -> None:
        """Bind the real resource teardown used by eviction/idle sweeps."""
        with self._lock:
            if name not in self._items:
                raise KeyError(name)
            self._items[name].unload = callback

    def touch(self, name: str, now: float | None = None) -> None:
        with self._lock:
            self._items[name].last_used = time.monotonic() if now is None else float(now)

    def _victims_for(self, target: Reservation) -> list[Reservation]:
        victims = []
        for item in self._items.values():
            if not item.loaded or not item.evictable or item.name == target.name:
                continue
            if target.exclusive_group and item.exclusive_group == target.exclusive_group:
                # Explicitly switching an implementation of the same role is allowed.
                victims.append(item)
                continue
            # A lower-priority request must never evict a more important resident
            # component (e.g. dashboard/cleanup may not knock out STT).
            if item.priority <= target.priority:
                victims.append(item)
        # Evict low-priority first; among equals, least recently used first.
        return sorted(victims, key=lambda x: (x.priority, x.last_used))

    def plan_load(self, name: str) -> dict:
        with self._lock:
            item = self._items[name]
            if item.loaded:
                return {"allowed": True, "need_mib": 0, "evict": []}
            need = item.charge_mib
            if need > self.usable_mib:
                return {"allowed": False, "need_mib": need, "evict": [], "reason": "resource exceeds usable budget"}

            must_evict: list[str] = []
            projected = self.used_mib + need
            for victim in self._victims_for(item):
                exclusive_conflict = bool(item.exclusive_group and victim.exclusive_group == item.exclusive_group)
                if projected <= self.usable_mib and not exclusive_conflict:
                    continue
                projected -= victim.charge_mib
                must_evict.append(victim.name)
            allowed = projected <= self.usable_mib
            return {
                "allowed": allowed,
                "need_mib": need,
                "evict": must_evict,
                "projected_mib": projected,
                "reason": None if allowed else "insufficient evictable budget",
            }

    def load(self, name: str) -> dict:
        with self._lock:
            item = self._items[name]
            if item.loaded:
                self.touch(name)
                return self.status()
            plan = self.plan_load(name)
            if not plan["allowed"]:
                raise MemoryBudgetError(
                    f"cannot load {name}: {plan.get('reason')}; need {plan['need_mib']} MiB, usable {self.usable_mib} MiB"
                )
            for victim_name in plan["evict"]:
                self.unload(victim_name)
            item.loaded = True
            self.touch(name)
            return self.status()

    def unload(self, name: str) -> dict:
        with self._lock:
            item = self._items[name]
            if item.loaded and item.unload is not None:
                item.unload()
            item.loaded = False
            item.last_used = time.monotonic()
            return self.status()

    def sweep_idle(self, now: float | None = None) -> list[str]:
        now = time.monotonic() if now is None else float(now)
        evicted: list[str] = []
        for item in tuple(self._items.values()):
            if not item.loaded or not item.evictable or item.idle_unload_s is None:
                continue
            if item.last_used and now - item.last_used >= item.idle_unload_s:
                self.unload(item.name)
                evicted.append(item.name)
        return evicted

    def reconcile(self) -> list[str]:
        """Return to budget after measured RSS changes.

        Low-priority resources are evicted first. If the single remaining
        protected workload itself exceeds the cap, status reports the violation
        instead of pretending the budget is satisfied.
        """
        evicted: list[str] = []
        while self.used_mib > self.usable_mib:
            victims = sorted(
                (x for x in self._items.values() if x.loaded and x.evictable),
                key=lambda x: (x.priority, x.last_used),
            )
            if not victims:
                break
            self.unload(victims[0].name)
            evicted.append(victims[0].name)
        return evicted

    def status(self) -> dict:
        with self._lock:
            resources = []
            for x in self._items.values():
                # Never deepcopy callbacks: bound methods may capture locks/processes
                # and are control-plane implementation details, not API state.
                d = {
                    "name": x.name,
                    "estimated_mib": x.estimated_mib,
                    "evictable": x.evictable,
                    "loaded": x.loaded,
                    "last_used": x.last_used,
                    "priority": x.priority,
                    "idle_unload_s": x.idle_unload_s,
                    "exclusive_group": x.exclusive_group,
                    "measured_mib": x.measured_mib,
                    "metadata": dict(x.metadata),
                    "unload_hook": bool(x.unload),
                    "charge_mib": x.charge_mib,
                }
                resources.append(d)
            return {
                "hard_limit_mib": self.hard_limit_mib,
                "fixed_mib": self.fixed_mib,
                "headroom_mib": self.headroom_mib,
                "usable_mib": self.usable_mib,
                "managed_used_mib": self.used_mib,
                "platform_reserved_mib": self.fixed_mib + self.headroom_mib + self.used_mib,
                "within_budget": self.used_mib <= self.usable_mib,
                "over_by_mib": max(0, self.used_mib - self.usable_mib),
                "resources": resources,
            }

