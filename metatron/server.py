from __future__ import annotations

from typing import Any

from .core import Metatron
from .models import model_catalog


class ProtocolError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class Dispatcher:
    def __init__(self, app: Metatron):
        self.app = app

    def dispatch(self, cmd: str, params: dict[str, Any] | None = None) -> Any:
        p = dict(params or {})
        if cmd == "status":
            return self.app.status()
        if cmd == "maintenance.tick":
            return self.app.maintenance_tick()
        if cmd == "events.tail":
            return self.app.bus.tail(int(p.get("after_seq", 0)), int(p.get("limit", 200)))
        if cmd == "events.live":
            return self.app.bus.live_tail(int(p.get("after_live_seq", 0)), int(p.get("limit", 256)))
        if cmd == "telemetry.latest":
            return self.app.telemetry.latest(int(p.get("limit", 100)))
        if cmd == "models.catalog":
            return model_catalog()

        if cmd == "speech.status":
            return self.app.speech.status()
        if cmd == "speech.start":
            return self.app.speech.start()
        if cmd == "speech.stop":
            return self.app.speech.stop()
        if cmd == "speech.events":
            return self.app.speech.events(bool(p.get("clear", False)))
        if cmd == "speech.request":
            return self.app.speech.request(str(p["command"]), dict(p.get("params") or {}), float(p.get("timeout_s", 30)))


        if cmd == "hardware.status":
            return self.app.hardware.status()
        if cmd == "hardware.refresh":
            return self.app.hardware.refresh()
        if cmd == "hardware.select":
            return self.app.hardware.select(str(p.get("workload") or "generic"), p.get("order"))
        if cmd == "hardware.policy":
            return self.app.hardware.set_policy(["NPU", "GPU", "CPU"], bool(p.get("allow_cpu", True)))
        if cmd == "hardware.windows_ml_catalog":
            return self.app.hardware.windows_ml_catalog()
        if cmd == "hardware.ensure_windows_ml":
            names = p.get("names")
            return self.app.hardware.ensure_windows_ml_providers(list(names) if isinstance(names, list) else None)
        if cmd == "hardware.report_actual":
            return self.app.hardware.report_actual(
                str(p.get("workload") or "generic"), kind=str(p["kind"]),
                provider=str(p.get("provider") or "runtime"), device=str(p.get("device") or ""),
                model=str(p.get("model") or ""),
            )

        if cmd == "settings.all":
            return self.app.settings.all()
        if cmd == "settings.get":
            return self.app.settings.get(p.get("section"))
        if cmd == "settings.set":
            section = str(p["section"])
            values = dict(p.get("values") or {})
            result = self.app.settings.set(section, values)
            # Apply live settings where safe. Restart-only settings are simply persisted.
            if section == "hardware":
                self.app.hardware.set_policy(["NPU", "GPU", "CPU"], bool(result.get("allow_cpu_fallback", True)))
            elif section == "presence":
                if "quality" in result:
                    self.app.set_presence_quality(str(result["quality"]))
            elif section == "memory":
                profile = str(result.get("profile") or self.app.config.memory_profile)
                if profile != self.app.config.memory_profile:
                    self.app.set_memory_profile(profile)
            elif section == "speech":
                was_running = self.app.speech.running
                self.app.speech.settings.enabled = bool(result.get("enabled", True))
                self.app.speech.settings.auto_start = bool(result.get("auto_start", False))
                self.app.speech.settings.model = str(result.get("model", "parakeet-unified-en-0.6b"))
                self.app.speech.settings.device_order = ("NPU", "GPU", "CPU")
                self.app.speech.settings.cleanup_enabled = bool(result.get("cleanup_enabled", True))
                self.app.speech.settings.hotkey = str(result.get("hotkey", "right ctrl"))
                self.app.speech.settings.mode = str(result.get("mode", "hold"))
                self.app.speech.settings.injection_method = str(result.get("injection_method", "paste"))
                if was_running:
                    self.app.speech.stop()
                    if self.app.speech.settings.enabled:
                        self.app.speech.start()
            elif section == "voice":
                self.app.tts.set_enabled(bool(result.get("tts_enabled", True)))
                self.app.tts.set_mode(str(result.get("tts_mode", "premium")))
                self.app.tts.set_threshold(int(result.get("tts_priority_threshold", 3)))
                self.app.tts.set_voice(str(result.get("tts_voice", "am_fenrir")), float(result.get("tts_speed", 0.96)))
            return result
        if cmd == "settings.reset":
            return self.app.settings.reset(p.get("section"))

        if cmd == "system.notify":
            return self.app.system_notify(
                str(p.get("text") or ""), priority=int(p.get("priority", 3)),
                category=str(p.get("category") or "system"), source=str(p.get("source") or "metatron"),
            )

        if cmd == "presence.snapshot":
            return self.app.presence.snapshot()
        if cmd == "presence.renderer_state":
            return self.app.presence.renderer_packet()
        if cmd == "presence.quality":
            return self.app.set_presence_quality(str(p["quality"]))
        if cmd == "presence.dashboard":
            return self.app.set_dashboard_open(bool(p.get("open", False)))
        if cmd == "presence.user_started":
            return self.app.presence.user_started()
        if cmd == "presence.user_level":
            return self.app.presence.user_level(float(p.get("level", 0.0)))
        if cmd == "presence.user_stopped":
            return self.app.presence.user_stopped()
        if cmd == "presence.asr_started":
            return self.app.presence.asr_started()
        if cmd == "presence.asr_partial":
            self.app.presence.asr_partial(str(p.get("text") or "")); return self.app.presence.snapshot()
        if cmd == "presence.asr_completed":
            return self.app.presence.asr_completed(str(p.get("text") or ""))
        if cmd == "presence.thinking_started":
            return self.app.presence.thinking_started(str(p.get("source", "assistant")))
        if cmd == "presence.thinking_finished":
            return self.app.presence.thinking_finished(str(p.get("source", "assistant")))
        if cmd == "presence.signal":
            self.app.presence.signal(str(p["kind"]), str(p.get("message") or ""), source=str(p.get("source", "system")))
            return self.app.presence.snapshot()

        if cmd == "tts.status":
            return self.app.tts.status()
        if cmd == "tts.enabled":
            return self.app.tts.set_enabled(bool(p.get("enabled", True)))
        if cmd == "tts.mode":
            return self.app.tts.set_mode(str(p["mode"]))
        if cmd == "tts.threshold":
            return self.app.tts.set_threshold(int(p["priority"]))
        if cmd == "tts.voice":
            return self.app.tts.set_voice(str(p.get("voice") or "am_fenrir"), p.get("speed"))
        if cmd == "tts.speak":
            return self.app.tts.enqueue(
                str(p.get("text") or ""), priority=int(p.get("priority", 3)),
                category=str(p.get("category") or "manual"), force=bool(p.get("force", False)),
            )
        if cmd == "tts.stop":
            return self.app.tts.stop_speaking()
        if cmd == "tts.barge_in":
            return self.app.barge_in()
        if cmd == "audio_focus.status":
            return self.app.audio_focus.status()

        if cmd == "agents.list":
            return self.app.agents.list()
        if cmd == "agent.detect":
            return self.app.agents.get(str(p["agent_id"])).detect()
        if cmd == "agent.start":
            return self.app.start_agent(str(p["agent_id"]))
        if cmd == "agent.stop":
            return self.app.stop_agent(str(p["agent_id"]))
        if cmd == "agent.submit":
            return self.app.submit_agent(str(p["agent_id"]), dict(p.get("task") or {}))
        if cmd == "agent.result":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "result", None)
            if fn is None:
                raise ProtocolError("unsupported", "agent does not expose a transient result")
            return fn()
        if cmd == "agent.events":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "events", None)
            if fn is None: return []
            return fn(bool(p.get("clear", False)))
        if cmd == "agent.pending_requests":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "pending_requests", None)
            if fn is None: return []
            return fn(bool(p.get("clear", False)))
        if cmd == "agent.respond":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "respond", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not expose interactive requests")
            fn(p["request_id"], p.get("result")); return {"ok": True}
        if cmd == "agent.interrupt":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "interrupt", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not support interruption")
            return fn(str(p["thread_id"]), p.get("turn_id"))

        if cmd == "agent.job_status":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "job_status", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not expose job status")
            return fn(p.get("job_id"))
        if cmd == "agent.cancel_job":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "cancel_job", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not expose job cancellation")
            return fn(p.get("job_id"))
        if cmd == "agent.jobs":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "list_jobs", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not expose jobs")
            return fn(int(p.get("limit", 50)))
        if cmd == "agent.stats":
            agent = self.app.agents.get(str(p["agent_id"]))
            fn = getattr(agent, "stats", None)
            if fn is None: raise ProtocolError("unsupported", "agent does not expose stats")
            return fn()

        if cmd == "tasks.list":
            return self.app.kanban.list(p.get("status"), int(p.get("limit", 200)), int(p.get("offset", 0)))
        if cmd == "tasks.get":
            return self.app.kanban.get(str(p["task_id"]))
        if cmd == "tasks.create":
            title = str(p.pop("title"))
            return self.app.kanban.create(title, **p)
        if cmd == "tasks.move":
            return self.app.kanban.move(str(p["task_id"]), str(p["status"]), str(p.get("actor", "user")))
        if cmd == "tasks.assign":
            return self.app.kanban.assign(str(p["task_id"]), p.get("agent_id"), str(p.get("actor", "user")))

        if cmd == "runs.create":
            return self.app.runs.create(str(p["task_id"]), p.get("agent_id"), dict(p.get("metadata") or {}))
        if cmd == "runs.list":
            return self.app.runs.list(p.get("task_id"), int(p.get("limit", 100)))
        if cmd == "runs.acquire":
            return self.app.runs.acquire(str(p["run_id"]), str(p["owner"]), float(p.get("ttl_s", 60)))
        if cmd == "runs.heartbeat":
            return self.app.runs.heartbeat(str(p["run_id"]), str(p["owner"]), float(p.get("ttl_s", 60)))
        if cmd == "runs.state":
            updates = {k: v for k, v in p.items() if k in ("usage", "exit_code")}
            return self.app.runs.set_state(str(p["run_id"]), str(p["state"]), str(p.get("actor", "system")), **updates)

        if cmd == "approval.request":
            return self.app.approvals.request(str(p["action"]), str(p.get("actor", "agent")), dict(p.get("payload") or {}), p.get("ttl_s", 600))
        if cmd == "approval.list":
            return self.app.approvals.list(p.get("status"), int(p.get("limit", 100)))
        if cmd == "approval.decide":
            return self.app.approvals.decide(str(p["approval_id"]), bool(p["approved"]), str(p.get("actor", "user")))

        if cmd == "memory.status":
            return self.app.memory.status()
        if cmd == "memory.plan":
            return self.app.memory.plan_load(str(p["name"]))
        if cmd == "memory.load":
            return self.app.memory.load(str(p["name"]))
        if cmd == "memory.touch":
            self.app.memory.touch(str(p["name"])); return self.app.memory.status()
        if cmd == "memory.unload":
            return self.app.memory.unload(str(p["name"]))
        if cmd == "memory.profile":
            return self.app.set_memory_profile(str(p["profile"]))
        if cmd == "memory.pressure_check":
            return self.app.apply_system_pressure(p.get("available_mib"))
        if cmd == "memory.measured":
            self.app.memory.set_measured_mib(str(p["name"]), float(p["mib"]))
            evicted = self.app.memory.reconcile()
            return {"evicted": evicted, "memory": self.app.memory.status()}

        if cmd == "schedules.list":
            return self.app.scheduler.list(bool(p.get("enabled_only", False)))
        if cmd == "schedules.create_interval":
            return self.app.scheduler.create_interval(
                str(p["label"]), dict(p.get("task_template") or {}), float(p["interval_s"]),
                p.get("agent_id"), p.get("first_run"),
            )
        if cmd == "schedules.due":
            return self.app.scheduler.due(p.get("now"))
        raise ProtocolError("unknown_cmd", f"unknown command {cmd!r}")
