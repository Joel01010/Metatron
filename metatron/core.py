from __future__ import annotations

import threading
import time
from typing import Any

from .approvals import ApprovalStore
from .config import AppConfig, MEMORY_PROFILES
from .db import Database
from .events import EventBus
from .presence import PresenceController
from .audio_focus import AudioFocusController
from .tts import TTSManager, TTSSettings, SpeechPriority
from .kanban import Kanban
from .memory import ModelBroker, Reservation
from .models import DEFAULT_MODELS, model_catalog
from .runs import RunStore
from .scheduler import Scheduler
from .telemetry import Telemetry, process_tree_rss_mib, system_memory
from .agents.registry import AgentRegistry
from .agents.hermes import HermesLocalAdapter, HermesCloudAdapter
from .agents.codex import CodexAdapter
from .agents.claude import ClaudeCodeAdapter
from .agents.opencode import OpenCodeAdapter
from .hardware import HardwareManager
from .settings import SettingsStore
from .speech import SpeechRuntime, SpeechSettings, speech_command_from_env


class Metatron:
    def __init__(self, config: AppConfig | None = None):
        self.config = config or AppConfig.default()
        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.config.data_dir / "metatron.sqlite3")
        self.bus = EventBus(self.db)
        self.kanban = Kanban(self.db, self.bus)
        self.approvals = ApprovalStore(self.db, self.bus)
        self.runs = RunStore(self.db, self.bus)
        self.scheduler = Scheduler(self.db, self.bus)
        self.telemetry = Telemetry(self.db, self.config.telemetry_retention_h)
        self.settings = SettingsStore(self.db, self.bus)
        self.hardware = HardwareManager(self.db, self.bus, winml_python=self.config.winml_python)
        self.memory = self._build_memory_broker(self.config.memory_profile)
        self.presence = PresenceController(self.bus)
        self.presence.set_quality(self.config.presence_quality, source="config")
        self.audio_focus = AudioFocusController(
            self.bus, suppress_during_tts=self.config.tts_echo_guard,
            tail_ms=self.config.tts_capture_tail_ms, barge_in=self.config.tts_barge_in,
        )
        self.tts = self._build_tts_manager()
        self.speech = self._build_speech_manager()
        if self.speech.settings.auto_start and self.speech.configured:
            threading.Thread(target=self._start_speech_safely, name="speech-autostart", daemon=True).start()
        self.agents = AgentRegistry()
        self._register_default_agents()
        self._bind_agent_eviction_hooks()
        self._sync_agents_to_db()
        self._stop = threading.Event()
        self._maintenance: threading.Thread | None = None
        if self.config.enable_background_maintenance:
            self._maintenance = threading.Thread(target=self._maintenance_loop, name="metatron-maint", daemon=True)
            self._maintenance.start()

    def _build_memory_broker(self, profile_name: str) -> ModelBroker:
        profile = MEMORY_PROFILES[profile_name]
        # Backend/pet are always-resident. UI is charged only while open by the
        # future Tauri host, so it is registered as a managed optional resource.
        fixed = profile.backend_target_mib + profile.pet_target_mib
        broker = ModelBroker(profile.hard_limit_mib, fixed_mib=fixed, headroom_mib=profile.reserve_headroom_mib)
        broker.register(Reservation(
            name="dashboard-webview", estimated_mib=max(1, profile.ui_target_mib or 1),
            evictable=True, priority=72, idle_unload_s=None, exclusive_group="ui",
            metadata={"kind": "ui"},
        ))
        broker.register(Reservation(
            name="presence-orb-renderer", estimated_mib=180,
            evictable=True, priority=85, idle_unload_s=None, exclusive_group="presence",
            metadata={"kind": "presence", "quality": "balanced"},
        ))
        for spec in DEFAULT_MODELS:
            estimate = spec.estimated_ram_mib
            idle = spec.idle_unload_s
            if spec.id == "kokoro-82m-tts":
                model_name = str(self.config.kokoro_model_path or "").lower()
                if ".int8." in model_name:
                    estimate = 260
                elif ".fp16." in model_name:
                    estimate = 330
                idle = self.config.tts_idle_unload_s
            broker.register(Reservation(
                spec.id, estimate,
                evictable=True,
                priority=spec.priority,
                idle_unload_s=idle,
                exclusive_group=spec.exclusive_group,
                metadata={"role": spec.role, "runtime": spec.runtime},
            ))
        # E.O.P. is a local orchestration service, not a coding-agent slot.
        # It may remain connected while one coding agent executes underneath it.
        broker.register(Reservation(
            name="agent:eop", estimated_mib=384, evictable=True, priority=80,
            idle_unload_s=None, exclusive_group="local-service",
            metadata={"role": "local-service"},
        ))
        # Coding runtimes are mutually constrained by max_local_agents. Their
        # estimates are replaced by measured process-tree RSS while running.
        for name, mib in (("agent:codex", 180), ("agent:claude-code", 220),
                          ("agent:opencode", 240)):
            broker.register(Reservation(
                name=name, estimated_mib=mib, evictable=True, priority=80,
                idle_unload_s=None, exclusive_group="local-agent",
                metadata={"role": "coding-agent"},
            ))
        # Reserve the always-on floating presence. The frontend will later
        # replace the estimate with measured WebView/GPU-process RSS.
        try:
            broker.load("presence-orb-renderer")
        except Exception:
            pass
        return broker


    def _build_tts_manager(self) -> TTSManager:
        return TTSManager(
            bus=self.bus,
            broker=self.memory,
            presence=self.presence,
            telemetry=self.telemetry,
            db=self.db,
            data_dir=self.config.data_dir,
            settings=TTSSettings(
                enabled=self.config.tts_enabled,
                mode=self.config.tts_mode,
                priority_threshold=self.config.tts_priority_threshold,
                voice=self.config.tts_voice,
                speed=self.config.tts_speed,
                playback=self.config.tts_playback,
            ),
            kokoro_python=self.config.kokoro_python,
            kokoro_model_path=self.config.kokoro_model_path,
            kokoro_voices_path=self.config.kokoro_voices_path,
            piper_bin=self.config.piper_bin,
            piper_model_path=self.config.piper_model_path,
            audio_focus=self.audio_focus,
        )

    def _build_speech_manager(self) -> SpeechRuntime:
        speech_cfg = self.settings.get("speech") or {}
        speech_cmd = speech_command_from_env()
        if not speech_cmd and self.config.speech_command:
            import shlex, os
            speech_cmd = shlex.split(self.config.speech_command, posix=os.name != "nt")
        return SpeechRuntime(
            command=speech_cmd, broker=self.memory, hardware=self.hardware, bus=self.bus, presence=self.presence,
            settings=SpeechSettings(
                enabled=bool(speech_cfg.get("enabled", self.config.speech_enabled)),
                auto_start=bool(speech_cfg.get("auto_start", self.config.speech_auto_start)),
                model=str(speech_cfg.get("model", self.config.speech_model)),
                device_order=("NPU", "GPU", "CPU"),
                cleanup_enabled=bool(speech_cfg.get("cleanup_enabled", True)),
                injection_method=str(speech_cfg.get("injection_method", self.config.speech_injection_method)),
                mode=str(speech_cfg.get("mode", self.config.speech_mode)),
                hotkey=str(speech_cfg.get("hotkey", self.config.speech_hotkey)),
            ),
            log_path=str(self.config.data_dir / "logs" / "speech.log"),
        )

    def _start_speech_safely(self) -> None:
        try:
            self.speech.start()
        except Exception as exc:
            self.bus.emit("speech.runtime.error", "speech", {"error": str(exc)})

    def _register_default_agents(self) -> None:
        logs = str(self.config.data_dir / "logs")
        self.agents.register(HermesLocalAdapter(
            id="eop", label="E.O.P. / Hermes Local", kind="hermes-local",
            base_url=self.config.eop_url, api_key=self.config.eop_api_key, remote=False,
            start_command=self.config.eop_start_command, cwd=self.config.eop_workspace))
        ezra_url = self.config.ezra_url
        if not ezra_url and self.config.ezra_host:
            ezra_url = f"http://{self.config.ezra_host}:9200"
        self.agents.register(HermesCloudAdapter(
            id="ezra", label="Ezra / Hermes Cloud", kind="hermes-cloud",
            base_url=ezra_url, api_key=self.config.ezra_api_key, remote=True))
        self.agents.register(CodexAdapter(log_dir=logs))
        self.agents.register(ClaudeCodeAdapter(log_dir=logs))
        self.agents.register(OpenCodeAdapter(log_dir=logs))


    def _bind_agent_eviction_hooks(self) -> None:
        """Make memory eviction stop the *real* local runtime, not just accounting.

        Ezra is remote and has no local reservation. E.O.P. only terminates when
        Metatron started its process; externally managed E.O.P. remains external.
        """
        for agent_id in ("eop", "codex", "claude-code", "opencode"):
            agent = self.agents.get(agent_id)
            self.memory.set_unload_callback(
                f"agent:{agent_id}",
                lambda agent=agent: agent.stop(),
            )

    def _sync_agents_to_db(self) -> None:
        now = time.time()
        for a in self.agents.list(include_detect=False):
            agent_id = a["id"]
            kind = a["kind"]
            label = a["label"]
            transport = "ssh" if agent_id == "ezra" else "local"
            self.db.execute(
                """INSERT INTO agents(id,kind,label,transport,created_at,updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET kind=excluded.kind,label=excluded.label,
                   transport=excluded.transport,updated_at=excluded.updated_at""",
                (agent_id, kind, label, transport, now, now),
            )

    def _maintenance_loop(self) -> None:
        next_telemetry = 0.0
        next_prune = 0.0
        while not self._stop.wait(self.config.scheduler_tick_s):
            now_wall = time.time()
            now_mono = time.monotonic()
            try:
                evicted = self.memory.sweep_idle(now_mono)
                evicted += self.memory.reconcile()
                for name in dict.fromkeys(evicted):
                    self.bus.emit("memory.eviction", "memory", {"resource": name, "reason": "maintenance"})
                self.tts.maintenance()
                self.approvals.expire(now_wall)
                self.runs.release_expired(now_wall)
                self._materialize_due_schedules(now_wall)
                if now_wall >= next_telemetry:
                    self.telemetry.sample_core(persist=True)
                    self._learn_agent_memory()
                    self._release_finished_transient_agents()
                    self.apply_system_pressure()
                    next_telemetry = now_wall + max(1.0, self.config.telemetry_interval_s)
                if now_wall >= next_prune:
                    self.telemetry.prune(now_wall)
                    self.db.prune_events(self.config.event_retention)
                    next_prune = now_wall + 900
            except Exception as exc:
                self.bus.emit("maintenance.error", "core", {"error": type(exc).__name__, "message": str(exc)[:500]})

    def _learn_agent_memory(self) -> None:
        for agent in self.agents.list(include_detect=False):
            pid = agent.get("pid")
            if not pid:
                continue
            rss = process_tree_rss_mib(int(pid))
            if rss is not None:
                self.telemetry.record(agent["id"], "rss", rss, "MiB")
                resource_name = f"agent:{agent['id']}"
                try:
                    self.memory.set_measured_mib(resource_name, rss)
                except KeyError:
                    pass
        evicted = self.memory.reconcile()
        for name in evicted:
            self.bus.emit("memory.eviction", "memory", {"resource": name, "reason": "measured-rss"})

    def _release_finished_transient_agents(self) -> None:
        for agent_id in self.agents.ids():
            if agent_id == "ezra":
                continue
            agent = self.agents.get(agent_id)
            if not bool(getattr(agent, "transient", False)):
                continue
            if agent.status().state.value != "running":
                try:
                    self.memory.unload(f"agent:{agent_id}")
                except KeyError:
                    pass

    def apply_system_pressure(self, available_mib: float | None = None) -> dict[str, Any]:
        """Reduce optional residency when Windows itself is under pressure.

        This is deliberately one-way: Metatron may reduce visual quality and
        unload optional models, but it does not auto-restore them later. That
        avoids oscillation and respects the user's explicit next action.
        """
        if available_mib is None:
            raw = system_memory().get("available_mib")
            available_mib = None if raw is None else float(raw)
        minimum = float(self.config.memory.min_system_available_mib)
        if available_mib is None or available_mib >= minimum:
            return {"pressure": False, "available_mib": available_mib, "minimum_mib": minimum, "evicted": []}

        evicted: list[str] = []
        # Cleanup is recomputable and is the first ML worker to sacrifice.
        for name in ("s1-mini-by-superwhisper", "kokoro-82m-tts", "piper-en-tts", "windows-sapi-tts"):
            if name == "kokoro-82m-tts" and self.tts.status().get("speaking"):
                continue
            try:
                resource = next((r for r in self.memory.status()["resources"] if r["name"] == name), None)
                if resource and resource["loaded"]:
                    self.memory.unload(name)
                    evicted.append(name)
            except Exception:
                pass

        # Rendering degrades instead of disappearing. One procedural shader at
        # reduced resolution is much cheaper than destroying the user's presence.
        if self.presence.snapshot().get("quality") != "eco":
            self.memory.set_estimated_mib("presence-orb-renderer", 90)
            self.presence.set_quality("eco", source="memory-pressure")

        self.bus.emit("memory.pressure", "memory", {
            "available_mib": available_mib,
            "minimum_mib": minimum,
            "evicted": evicted,
            "action": "eco-presence",
        })
        return {"pressure": True, "available_mib": available_mib, "minimum_mib": minimum, "evicted": evicted}

    def _materialize_due_schedules(self, now: float | None = None) -> list[dict[str, Any]]:
        created = []
        for item in self.scheduler.due(now):
            template = dict(item.get("task_template") or {})
            title = str(template.pop("title", item["label"]))
            template.setdefault("status", "ready")
            if item.get("agent_id") and "agent_id" not in template:
                template["agent_id"] = item["agent_id"]
            metadata = dict(template.get("metadata") or {})
            metadata.update({"schedule_id": item["id"], "missed_intervals": item.get("missed_intervals", 0)})
            template["metadata"] = metadata
            task = self.kanban.create(title, **template)
            created.append(task)
        return created

    def _active_local_agent_slots(self, exclude: str | None = None) -> set[str]:
        out: set[str] = set()
        for r in self.memory.status()["resources"]:
            if not r["loaded"] or r.get("metadata", {}).get("role") != "coding-agent":
                continue
            agent_id = r["name"].split(":", 1)[1]
            if agent_id != exclude:
                out.add(agent_id)
        return out

    def start_agent(self, agent_id: str) -> dict:
        agent = self.agents.get(agent_id)
        resource_name = f"agent:{agent_id}"
        transient = bool(getattr(agent, "transient", False))
        # Transient adapters (Claude print mode) do not reserve RAM until a task
        # actually launches. Ezra is remote and does not count locally.
        if agent_id != "ezra" and not transient:
            loaded_agent_ids = self._active_local_agent_slots(exclude=agent_id)
            limit = self.config.memory.max_local_agents
            if len(loaded_agent_ids) >= limit:
                labels = {a["id"]: a["label"] for a in self.agents.list(include_detect=False)}
                names = ", ".join(labels.get(i, i) for i in sorted(loaded_agent_ids))
                raise RuntimeError(f"local-agent limit ({limit}) reached; stop {names} first")
            available = system_memory().get("available_mib")
            minimum = self.config.memory.min_system_available_mib
            if available is not None and float(available) < minimum:
                raise RuntimeError(
                    f"system memory guard: only {float(available):.0f} MiB available; {minimum} MiB required"
                )
            self.memory.load(resource_name)
        try:
            status = agent.start().to_dict()
        except Exception:
            if agent_id != "ezra" and not transient:
                self.memory.unload(resource_name)
            raise
        if status["state"] == "error" and agent_id != "ezra" and not transient:
            self.memory.unload(resource_name)
        self.bus.emit("agent.started", "core", {"agent_id": agent_id, "state": status["state"]})
        return status

    def submit_agent(self, agent_id: str, task: dict[str, Any]) -> dict:
        agent = self.agents.get(agent_id)
        transient = bool(getattr(agent, "transient", False))
        resource_name = f"agent:{agent_id}"
        if agent_id != "ezra":
            loaded = self._active_local_agent_slots(exclude=agent_id)
            # E.O.P. itself is a local service, so only coding-agent adapters
            # consume execution slots.
            counts_slot = agent_id in {"codex", "claude-code", "opencode"}
            if counts_slot and len(loaded) >= self.config.memory.max_local_agents:
                raise RuntimeError("local-agent concurrency limit reached")
            self.memory.load(resource_name)
        try:
            result = agent.submit(task)
        except Exception:
            if agent_id != "ezra" and transient:
                self.memory.unload(resource_name)
            raise
        if not result.get("accepted", False) and agent_id != "ezra" and transient:
            self.memory.unload(resource_name)
        self.bus.emit("agent.submitted", "core", {"agent_id": agent_id, "accepted": bool(result.get("accepted"))})
        return result

    def stop_agent(self, agent_id: str) -> dict:
        status = self.agents.get(agent_id).stop().to_dict()
        if agent_id != "ezra":
            name = f"agent:{agent_id}"
            try:
                self.memory.unload(name)
            except KeyError:
                pass
        self.bus.emit("agent.stopped", "core", {"agent_id": agent_id, "state": status["state"]})
        return status

    def set_memory_profile(self, profile_name: str) -> dict:
        profile_name = profile_name.strip().lower()
        if profile_name not in MEMORY_PROFILES:
            raise ValueError(f"unknown memory profile {profile_name!r}")
        loaded = [x["name"] for x in self.memory.status()["resources"] if x["loaded"]]
        # Rebuild the policy then re-admit currently loaded resources. If a
        # tighter profile cannot hold one, it remains unloaded rather than overcommit.
        self.config.memory_profile = profile_name
        new_broker = self._build_memory_broker(profile_name)
        for name in loaded:
            if name in {x["name"] for x in new_broker.status()["resources"]}:
                try:
                    new_broker.load(name)
                except Exception:
                    pass
        self.speech.close()
        self.tts.close()
        self.memory = new_broker
        self._bind_agent_eviction_hooks()
        self.tts = self._build_tts_manager()
        self.speech = self._build_speech_manager()
        if self.speech.settings.auto_start and self.speech.configured:
            threading.Thread(target=self._start_speech_safely, name="speech-autostart", daemon=True).start()
        self.bus.emit("memory.profile", "core", {"profile": profile_name})
        return self.memory.status()

    def maintenance_tick(self) -> dict[str, Any]:
        now_wall, now_mono = time.time(), time.monotonic()
        evicted = self.memory.sweep_idle(now_mono)
        evicted += self.memory.reconcile()
        for name in dict.fromkeys(evicted):
            self.bus.emit("memory.eviction", "memory", {"resource": name, "reason": "manual-tick"})
        self.tts.maintenance()
        expired = self.approvals.expire(now_wall)
        leases = self.runs.release_expired(now_wall)
        tasks = self._materialize_due_schedules(now_wall)
        pressure = self.apply_system_pressure()
        return {"evicted": evicted, "expired_approvals": expired, "released_leases": leases, "scheduled_tasks": tasks, "pressure": pressure}

    def close(self) -> None:
        self._stop.set()
        if self._maintenance and self._maintenance.is_alive():
            self._maintenance.join(timeout=2)
        self.speech.close()
        self.tts.close()
        self.audio_focus.close()
        self.agents.stop_all()
        self.telemetry.close()
        self.db.close()

    def set_presence_quality(self, quality: str) -> dict[str, Any]:
        q = str(quality).lower()
        estimates = {"eco": 90, "balanced": 180, "spectacle": 280}
        if q not in estimates:
            raise ValueError("quality must be eco, balanced, or spectacle")
        self.memory.set_estimated_mib("presence-orb-renderer", estimates[q])
        snap = self.presence.set_quality(q, source="user")
        evicted = self.memory.reconcile()
        for name in evicted:
            self.bus.emit("memory.eviction", "memory", {"resource": name, "reason": "presence-quality"})
        if not self.memory.status()["within_budget"]:
            self.bus.emit("memory.pressure", "memory", {"reason": "presence-quality", "quality": q})
        return {"presence": snap, "memory": self.memory.status(), "evicted": evicted}

    def set_dashboard_open(self, opened: bool) -> dict[str, Any]:
        if opened:
            self.memory.load("dashboard-webview")
        else:
            self.memory.unload("dashboard-webview")
        snap = self.presence.set_dashboard_open(bool(opened))
        return {"presence": snap, "memory": self.memory.status()}

    def barge_in(self) -> dict[str, Any]:
        """Interrupt Metatron speech and immediately give microphone focus to the user."""
        tts = self.tts.stop_speaking()
        focus = self.audio_focus.user_barge_in()
        self.bus.emit("tts.barge_in", "user", {})
        return {"tts": tts, "audio_focus": focus}

    def system_notify(
        self, text: str, *, priority: int = int(SpeechPriority.IMPORTANT),
        category: str = "system", source: str = "metatron",
    ) -> dict[str, Any]:
        priority = max(0, min(4, int(priority)))
        payload = {"text": str(text)[:2000], "priority": priority, "category": str(category)[:80]}
        ev = self.bus.emit("system.reply", source, payload)
        if priority >= int(SpeechPriority.IMPORTANT):
            kind = "error" if priority >= int(SpeechPriority.URGENT) else "success"
            self.bus.emit("presence.signal", source, {"kind": kind, "message": str(text)[:500]})
        return {"event_seq": ev.seq, **payload}

    def status(self) -> dict:
        telemetry = self.telemetry.sample_core(persist=False)
        return {
            "version": "1.0.0",
            "memory_profile": self.config.memory_profile,
            "memory": self.memory.status(),
            "telemetry": telemetry,
            "hardware": self.hardware.status(),
            "settings": self.settings.all(),
            "presence": self.presence.snapshot(),
            "audio_focus": self.audio_focus.status(),
            "tts": self.tts.status(),
            "speech": self.speech.status(),
            "agents": self.agents.list(),
            "models": model_catalog(),
            "tasks": self.kanban.counts(),
            "pending_approvals": self.approvals.count_pending(),
        }
