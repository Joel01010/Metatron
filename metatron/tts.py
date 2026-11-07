from __future__ import annotations

import base64
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Protocol

from .audio import wav_envelope
from .audio_focus import AudioFocusController
from .events import Event, EventBus
from .db import Database
from .memory import MemoryBudgetError, ModelBroker
from .presence import PresenceController
from .telemetry import Telemetry, process_tree_charge_mib
from .workers import JsonlWorkerSupervisor, WorkerError


class SpeechPriority(IntEnum):
    SILENT = 0
    VISUAL = 1
    NOTIFICATION = 2
    IMPORTANT = 3
    URGENT = 4


@dataclass(slots=True)
class TTSSettings:
    enabled: bool = True
    mode: str = "premium"  # premium | light | off
    priority_threshold: int = int(SpeechPriority.IMPORTANT)
    voice: str = "am_fenrir"
    speed: float = 0.96
    playback: bool = True


@dataclass(slots=True)
class SynthesisResult:
    provider: str
    voice: str
    path: str
    duration_ms: float
    envelope: dict[str, Any]


class TTSProvider(Protocol):
    id: str
    resource_name: str

    def available(self) -> bool: ...
    def synthesize(self, text: str, output_path: Path, voice: str, speed: float) -> Path: ...
    def stop(self) -> None: ...


class KokoroOnnxProvider:
    id = "kokoro-onnx"
    resource_name = "kokoro-82m-tts"

    def __init__(self, broker: ModelBroker, python_exe: str, model_path: str, voices_path: str, worker_script: str, log_path: str):
        self.python_exe = str(python_exe or sys.executable)
        self.model_path = str(model_path or "")
        self.voices_path = str(voices_path or "")
        self.worker_script = str(worker_script)
        self._worker: JsonlWorkerSupervisor | None = None
        self._broker = broker
        self._log_path = log_path

    def available(self) -> bool:
        return bool(
            self.model_path and self.voices_path
            and Path(self.model_path).is_file()
            and Path(self.voices_path).is_file()
            and Path(self.worker_script).is_file()
            and (Path(self.python_exe).is_file() or bool(shutil.which(self.python_exe)))
        )

    def _supervisor(self) -> JsonlWorkerSupervisor:
        if self._worker is None:
            self._worker = JsonlWorkerSupervisor(
                name=self.resource_name,
                command=[self.python_exe, self.worker_script, "--model", self.model_path, "--voices", self.voices_path],
                broker=self._broker,
                log_path=self._log_path,
                request_timeout_s=30.0,
            )
        return self._worker

    @property
    def pid(self) -> int | None:
        return self._worker.pid if self._worker is not None else None

    def synthesize(self, text: str, output_path: Path, voice: str, speed: float) -> Path:
        if not self.available():
            raise RuntimeError("Kokoro model/voices are not configured")
        result = self._supervisor().request("synthesize", {
            "text": text,
            "output_path": str(output_path),
            "voice": voice,
            "speed": speed,
        }, timeout_s=45.0)
        p = Path(str((result or {}).get("path") or output_path))
        if not p.is_file():
            raise RuntimeError("Kokoro worker did not produce audio")
        return p

    def stop(self) -> None:
        if self._worker is not None:
            self._worker.stop()


class PiperProvider:
    id = "piper"
    resource_name = "piper-en-tts"

    def __init__(self, broker: ModelBroker, binary: str, model_path: str):
        self.broker = broker
        self.binary = str(binary or "")
        self.model_path = str(model_path or "")

    def available(self) -> bool:
        exe = shutil.which(self.binary) if self.binary else None
        if not exe and self.binary and Path(self.binary).is_file():
            exe = self.binary
        return bool(exe and self.model_path and Path(self.model_path).is_file())

    def synthesize(self, text: str, output_path: Path, voice: str, speed: float) -> Path:
        exe = shutil.which(self.binary) if self.binary else None
        exe = exe or (self.binary if self.binary and Path(self.binary).is_file() else None)
        if not exe or not Path(self.model_path).is_file():
            raise RuntimeError("Piper binary/model are not configured")
        self.broker.load(self.resource_name)
        try:
            proc = subprocess.run(
                [str(exe), "--model", self.model_path, "--output_file", str(output_path)],
                input=text, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                encoding="utf-8", timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or "Piper failed")[-1000:])
            if not output_path.is_file():
                raise RuntimeError("Piper produced no WAV file")
            return output_path
        finally:
            self.broker.unload(self.resource_name)

    def stop(self) -> None:
        try:
            self.broker.unload(self.resource_name)
        except Exception:
            pass


class WindowsSapiProvider:
    """Zero-download fallback. Not the premium voice, but always useful on Windows."""
    id = "windows-sapi"
    resource_name = "windows-sapi-tts"

    def __init__(self, broker: ModelBroker):
        self.broker = broker
        self.powershell = shutil.which("powershell.exe") or shutil.which("powershell")

    def available(self) -> bool:
        return os.name == "nt" and bool(self.powershell)

    def synthesize(self, text: str, output_path: Path, voice: str, speed: float) -> Path:
        if not self.available():
            raise RuntimeError("Windows SAPI unavailable")
        self.broker.load(self.resource_name)
        env = os.environ.copy()
        env["METATRON_TTS_TEXT_B64"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
        env["METATRON_TTS_OUTPUT"] = str(output_path)
        # Prefer any installed male voice. This remains an emergency fallback;
        # premium Metatron speech should come from Kokoro.
        script = r'''
Add-Type -AssemblyName System.Speech
$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($env:METATRON_TTS_TEXT_B64))
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
$m=$s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Gender -eq 'Male'} | Select-Object -First 1
if($m){$s.SelectVoice($m.VoiceInfo.Name)}
$s.Rate=-1
$s.Volume=100
$s.SetOutputToWaveFile($env:METATRON_TTS_OUTPUT)
$s.Speak($t)
$s.Dispose()
'''
        try:
            proc = subprocess.run(
                [str(self.powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode != 0 or not output_path.is_file():
                raise RuntimeError((proc.stderr or b"SAPI failed").decode("utf-8", "replace")[-1000:])
            return output_path
        finally:
            self.broker.unload(self.resource_name)

    def stop(self) -> None:
        try:
            self.broker.unload(self.resource_name)
        except Exception:
            pass


class TTSManager:
    """Priority-gated local speech with bounded queue and orb synchronization."""

    def __init__(
        self,
        *,
        bus: EventBus,
        broker: ModelBroker,
        presence: PresenceController,
        telemetry: Telemetry,
        db: Database | None,
        data_dir: Path,
        settings: TTSSettings,
        kokoro_python: str = "",
        kokoro_model_path: str = "",
        kokoro_voices_path: str = "",
        piper_bin: str = "",
        piper_model_path: str = "",
        providers: list[TTSProvider] | None = None,
        audio_focus: AudioFocusController | None = None,
    ):
        self.bus = bus
        self.broker = broker
        self.presence = presence
        self.telemetry = telemetry
        self.db = db
        self.audio_focus = audio_focus
        self.data_dir = Path(data_dir)
        self.audio_dir = self.data_dir / "tts"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        if self.db is not None:
            saved = self.db.get_setting("tts", {}) or {}
            if isinstance(saved, dict):
                self.settings.enabled = bool(saved.get("enabled", self.settings.enabled))
                mode = str(saved.get("mode", self.settings.mode))
                self.settings.mode = mode if mode in {"premium", "light", "off"} else self.settings.mode
                self.settings.priority_threshold = max(0, min(4, int(saved.get("priority_threshold", self.settings.priority_threshold))))
                self.settings.voice = str(saved.get("voice", self.settings.voice))
                self.settings.speed = max(0.7, min(1.3, float(saved.get("speed", self.settings.speed))))
                self.settings.playback = bool(saved.get("playback", self.settings.playback))
        worker_script = Path(__file__).resolve().parents[1] / "scripts" / "kokoro_onnx_worker.py"
        self.providers: list[TTSProvider] = providers or [
            KokoroOnnxProvider(
                broker, kokoro_python, kokoro_model_path, kokoro_voices_path, str(worker_script),
                str(self.data_dir / "logs" / "kokoro-tts.log"),
            ),
            PiperProvider(broker, piper_bin, piper_model_path),
            WindowsSapiProvider(broker),
        ]
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=8)
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self._play_stop = threading.Event()
        self._lock = threading.RLock()
        self._last_error = ""
        self._last_provider = ""
        self._unsubscribe = self.bus.subscribe(self._on_event)

    def _on_event(self, ev: Event) -> None:
        # Only genuinely important control-plane events speak automatically.
        # Routine agent logs, telemetry, chat replies and Kanban movement stay silent.
        p = ev.payload
        if ev.topic == "system.reply":
            self.enqueue(
                str(p.get("text") or ""),
                priority=int(p.get("priority", SpeechPriority.IMPORTANT)),
                category=str(p.get("category") or "system"),
            )
        elif ev.topic == "approval.requested":
            action = str(p.get("action") or "an action").replace("_", " ")
            self.enqueue(f"Approval required for {action}.", priority=3, category="approval")
        elif ev.topic == "run.state" and str(p.get("to")) == "failed":
            self.enqueue("A task run has failed. Review is required.", priority=4, category="task-failure")
        elif ev.topic == "maintenance.error":
            self.enqueue("Metatron encountered a background service error.", priority=4, category="system-error")
        elif ev.topic == "agent.started" and str(p.get("state")) == "error":
            agent = str(p.get("agent_id") or "agent")
            self.enqueue(f"{agent} failed to start.", priority=4, category="agent-error")

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(target=self._queue_loop, name="metatron-tts", daemon=True)
            self._worker.start()

    def _save_settings(self) -> None:
        if self.db is not None:
            self.db.set_setting("tts", asdict(self.settings))

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.settings.enabled = bool(enabled)
        self._save_settings()
        if not enabled:
            self.stop_speaking()
            self._drain_queue()
            for p in self.providers:
                p.stop()
        self.bus.emit("tts.settings", "tts", self.status())
        return self.status()

    def set_mode(self, mode: str) -> dict[str, Any]:
        m = str(mode).lower()
        if m not in {"premium", "light", "off"}:
            raise ValueError("TTS mode must be premium, light, or off")
        self.settings.mode = m
        self._save_settings()
        if m == "off":
            self.set_enabled(False)
        else:
            self.settings.enabled = True
            self._save_settings()
        self.bus.emit("tts.settings", "tts", self.status())
        return self.status()

    def set_threshold(self, priority: int) -> dict[str, Any]:
        self.settings.priority_threshold = max(0, min(4, int(priority)))
        self._save_settings()
        self.bus.emit("tts.settings", "tts", self.status())
        return self.status()

    def set_voice(self, voice: str, speed: float | None = None) -> dict[str, Any]:
        self.settings.voice = str(voice or "am_fenrir")
        if speed is not None:
            self.settings.speed = max(0.7, min(1.3, float(speed)))
        self._save_settings()
        self.bus.emit("tts.settings", "tts", self.status())
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            **asdict(self.settings),
            "speaking": self._speaking.is_set(),
            "queue_depth": self._queue.qsize(),
            "providers": [{"id": p.id, "available": bool(p.available()), "resource": p.resource_name} for p in self.providers],
            "last_provider": self._last_provider,
            "last_error": self._last_error,
        }

    def enqueue(self, text: str, *, priority: int = 3, category: str = "system", force: bool = False) -> dict[str, Any]:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            return {"queued": False, "reason": "empty"}
        if not force:
            if not self.settings.enabled or self.settings.mode == "off":
                return {"queued": False, "reason": "disabled"}
            if int(priority) < int(self.settings.priority_threshold):
                return {"queued": False, "reason": "below-threshold"}
        item = {
            "id": uuid.uuid4().hex,
            "text": clean[:1200],
            "priority": max(0, min(4, int(priority))),
            "category": str(category)[:80],
            "force": bool(force),
        }
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            # Important/urgent speech may replace one stale queued item. We never
            # allow an unbounded verbal backlog.
            if item["priority"] >= int(SpeechPriority.IMPORTANT):
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(item)
                except queue.Empty:
                    return {"queued": False, "reason": "queue-full"}
            else:
                return {"queued": False, "reason": "queue-full"}
        self.bus.emit("tts.queued", "tts", {k: item[k] for k in ("id", "priority", "category")})
        self._ensure_worker()
        return {"queued": True, "id": item["id"]}

    def _provider_order(self) -> list[TTSProvider]:
        if self.settings.mode == "light":
            order = ("piper", "windows-sapi")
        else:
            order = ("kokoro-onnx", "piper", "windows-sapi")
        by_id = {p.id: p for p in self.providers}
        preferred = [by_id[x] for x in order if x in by_id]
        preferred.extend(p for p in self.providers if p.id not in order)
        return preferred

    def synthesize(self, text: str) -> SynthesisResult:
        output = self.audio_dir / f"tts-{int(time.time()*1000)}-{uuid.uuid4().hex[:8]}.wav"
        errors: list[str] = []
        start = time.perf_counter()
        chosen: TTSProvider | None = None
        for provider in self._provider_order():
            if not provider.available():
                continue
            try:
                chosen = provider
                provider.synthesize(text, output, self.settings.voice, self.settings.speed)
                break
            except (MemoryBudgetError, WorkerError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
                errors.append(f"{provider.id}: {exc}")
                try:
                    provider.stop()
                except Exception:
                    pass
                chosen = None
                continue
        if chosen is None:
            output.unlink(missing_ok=True)
            raise RuntimeError("no TTS provider succeeded" + (": " + " | ".join(errors) if errors else ""))
        env = wav_envelope(output, hz=30)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.telemetry.record("tts", "synthesis_latency", elapsed_ms, "ms", {"provider": chosen.id})
        self.telemetry.record("tts", "audio_duration", float(env["duration_ms"]), "ms", {"provider": chosen.id})
        self._last_provider = chosen.id
        return SynthesisResult(
            provider=chosen.id,
            voice=self.settings.voice,
            path=str(output),
            duration_ms=float(env["duration_ms"]),
            envelope=env,
        )

    def _queue_loop(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                # Exit when no work remains; no permanent TTS thread needed.
                if self._queue.empty() and not self._speaking.is_set():
                    return
                continue
            try:
                result = self.synthesize(item["text"])
                self._play(result, item)
                self._last_error = ""
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {exc}"
                self.bus.emit("tts.error", "tts", {"message": self._last_error[:1000]})
                self.presence.signal("warning", "Text-to-speech is unavailable.", source="tts")

    def _play(self, result: SynthesisResult, item: dict[str, Any]) -> None:
        self._speaking.set()
        self._play_stop.clear()
        if self.audio_focus is not None:
            self.audio_focus.tts_started()
        self.presence.tts_started(result.provider, result.voice, result.duration_ms)
        self.bus.emit("tts.audio", "tts", {
            "id": item["id"], "path": result.path, "duration_ms": result.duration_ms,
            "provider": result.provider, "voice": result.voice,
            # Frontend may play this itself later. The envelope stays compact.
            "envelope_hz": result.envelope.get("hz", 30),
        })
        start = time.monotonic()
        levels = list(result.envelope.get("levels") or [])
        winsound_module = None
        audio_started = False
        if self.settings.playback and os.name == "nt":
            try:
                import winsound
                # PlaySound's supported interruptible pattern is asynchronous
                # playback followed by PlaySound(None, 0). A synchronous call in
                # another thread can wait until the clip ends before the stop is
                # observed on some Windows audio stacks.
                winsound.PlaySound(
                    result.path,
                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                )
                winsound_module = winsound
                audio_started = True
            except Exception as exc:
                self._last_error = f"playback: {exc}"
        try:
            for point in levels:
                if self._play_stop.is_set():
                    break
                target = float(point["t_ms"]) / 1000.0
                delay = target - (time.monotonic() - start)
                if delay > 0:
                    self._play_stop.wait(delay)
                if self._play_stop.is_set():
                    break
                self.presence.tts_level(float(point["level"]), float(point["t_ms"]))
            # Keep the state machine alive through the advertised audio duration,
            # even if the 30 Hz envelope's final point lands slightly early.
            if audio_started and not self._play_stop.is_set():
                remaining = result.duration_ms / 1000.0 - (time.monotonic() - start)
                if remaining > 0:
                    self._play_stop.wait(remaining)
        finally:
            if audio_started and winsound_module is not None:
                try:
                    winsound_module.PlaySound(None, 0)
                except Exception:
                    pass
        stopped = self._play_stop.is_set()
        self.presence.tts_finished(stopped=stopped)
        if self.audio_focus is not None:
            self.audio_focus.tts_finished()
        self._speaking.clear()
        try:
            Path(result.path).unlink(missing_ok=True)
        except OSError:
            pass

    def stop_speaking(self) -> dict[str, Any]:
        self._play_stop.set()
        if os.name == "nt":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass
        if self._speaking.is_set():
            self.presence.tts_finished(stopped=True)
            self._speaking.clear()
        if self.audio_focus is not None:
            self.audio_focus.tts_finished()
        return self.status()

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def maintenance(self) -> None:
        # Learn real premium-worker RSS so the governor can replace estimates.
        for provider in self.providers:
            pid = getattr(provider, "pid", None)
            if pid:
                measured, measure_kind = process_tree_charge_mib(int(pid))
                if measured is not None:
                    try:
                        self.broker.set_measured_mib(provider.resource_name, measured)
                        metadata = {"measurement_kind": measure_kind}
                        worker = getattr(provider, "_worker", None)
                        if worker is not None:
                            peak = worker.peak_memory()
                            if peak:
                                metadata.update(peak)
                                self.telemetry.record("tts", "job_peak_commit", peak["peak_job_mib"], "MiB", {"provider": provider.id})
                        self.broker.set_metadata(provider.resource_name, **metadata)
                        self.telemetry.record(
                            "tts", measure_kind, measured, "MiB", {"provider": provider.id}
                        )
                    except KeyError:
                        pass
        evicted = self.broker.reconcile()
        for name in evicted:
            self.bus.emit("memory.eviction", "tts", {"resource": name, "reason": "tts-rss"})
        # Remove stale WAVs left by crashes.
        cutoff = time.time() - 3600
        try:
            for p in self.audio_dir.glob("tts-*.wav"):
                try:
                    if p.stat().st_mtime < cutoff:
                        p.unlink(missing_ok=True)
                except OSError:
                    pass
        except OSError:
            pass

    def close(self) -> None:
        self._stop.set()
        self.stop_speaking()
        self._drain_queue()
        for p in self.providers:
            try:
                p.stop()
            except Exception:
                pass
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=2)
        self._unsubscribe()
