from __future__ import annotations

import collections
import json
import os
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .hardware import HardwareManager
from .env import child_environment
from .job import owned_job
from .memory import ModelBroker


def _split_command(raw: str) -> list[str]:
    raw = (raw or '').strip()
    if not raw:
        return []
    parts = shlex.split(raw, posix=os.name != 'nt')
    if os.name == 'nt':
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] == '"' else p for p in parts]
    return parts


@dataclass(slots=True)
class SpeechSettings:
    enabled: bool = True
    auto_start: bool = False
    model: str = 'parakeet-unified-en-0.6b'
    device_order: tuple[str, ...] = ('NPU', 'GPU', 'CPU')
    cleanup_enabled: bool = True
    injection_method: str = 'paste'
    mode: str = 'hold'
    hotkey: str = 'right ctrl'
    privacy_pause_enabled: bool = True
    context_awareness: bool = True
    dictionary_enabled: bool = True
    default_context_profile: str = 'general'


@dataclass(slots=True)
class SpeechRuntime:
    """Supervises a JSON-lines STT sidecar without importing its ML stack.

    Compatible engines emit request responses with ``id`` plus events such as
    ``state`` and ``level``.  Heavy OpenVINO/ORT code therefore remains in a
    disposable process and can be fully reclaimed under memory pressure.
    """

    command: list[str]
    broker: ModelBroker
    hardware: HardwareManager
    bus: Any
    presence: Any
    settings: SpeechSettings = field(default_factory=SpeechSettings)
    log_path: str | None = None
    app_policy: Callable[[str], dict[str, Any]] | None = None
    vocabulary_provider: Callable[[], list[dict[str, Any]]] | None = None
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _reader: threading.Thread | None = field(default=None, init=False, repr=False)
    _stderr: Any = field(default=None, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    _pending: dict[int, threading.Event] = field(default_factory=dict, init=False, repr=False)
    _responses: dict[int, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _events: collections.deque = field(default_factory=lambda: collections.deque(maxlen=512), init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _selected_device: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _device_candidates: list[str] = field(default_factory=list, init=False, repr=False)
    _actual_device: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _job: object | None = field(default=None, init=False, repr=False)
    _last_state: str = field(default='OFFLINE', init=False, repr=False)
    _model_reservation: str = field(default='parakeet-unified-en-0.6b', init=False, repr=False)
    _last_transcript_signature: str = field(default='', init=False, repr=False)
    _last_transcript_at: float = field(default=0.0, init=False, repr=False)
    _active_app: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _privacy_runtime_supported: bool | None = field(default=None, init=False, repr=False)
    _privacy_rule_signature: str = field(default='', init=False, repr=False)
    _vocabulary_runtime_supported: bool | None = field(default=None, init=False, repr=False)

    @property
    def configured(self) -> bool:
        return bool(self.command)

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self.running and self._proc else None

    def _reservation_for_model(self, model: str) -> str:
        if model.startswith('orukeet'):
            return 'orukeet-int8'
        return 'parakeet-unified-en-0.6b'

    def start(self) -> dict[str, Any]:
        if not self.settings.enabled:
            raise RuntimeError('speech input is disabled')
        if not self.configured:
            raise RuntimeError('speech runtime is not configured; run Setup-SpeechRuntime.ps1 or set METATRON_SPEECH_CMD')
        with self._lock:
            if self.running:
                return self.status()
            self._model_reservation = self._reservation_for_model(self.settings.model)
            self.broker.load(self._model_reservation)
            stderr: Any = subprocess.DEVNULL
            if self.log_path:
                p = Path(self.log_path); p.parent.mkdir(parents=True, exist_ok=True)
                self._stderr = open(p, 'ab', buffering=0); stderr = self._stderr
            flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0
            try:
                self._proc = subprocess.Popen(
                    self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=stderr, text=True, encoding='utf-8', bufsize=1,
                    creationflags=flags, env=child_environment(),
                )
                self._job = owned_job('Metatron-speech')
                self._job.assign_pid(self._proc.pid)
            except Exception:
                self.broker.unload(self._model_reservation)
                raise
            self._reader = threading.Thread(target=self._read_loop, name='metatron-speech', daemon=True)
            self._reader.start()
        # Most compatible engines answer ping and list_ov_devices.  Configure
        # only after protocol startup so fallback is explicit and observable.
        self._privacy_runtime_supported = None
        self._privacy_rule_signature = ''
        self.request('ping', {}, timeout_s=10)
        self._configure_best_device()
        self._apply_config()
        self.refresh_personalization()
        self.bus.emit('speech.runtime.started', 'speech', {'pid': self.pid, 'device': self._actual_device})
        return self.status()

    def _configure_best_device(self) -> None:
        sidecar_devices: list[str] = []
        try:
            result = self.request('list_ov_devices', {}, timeout_s=10) or {}
            sidecar_devices = [str(x).upper() for x in result.get('devices', [])]
        except Exception:
            pass
        # Runtime capability is authoritative. Keep class order fixed and try
        # every class the sidecar actually exposes. A sidecar that only exposes
        # NPU/CPU cannot satisfy a GPU fallback; that is surfaced in status.
        desired = [str(x).upper() for x in self.settings.device_order]
        self._device_candidates = [x for x in desired if x in sidecar_devices]
        if not self._device_candidates:
            raise RuntimeError(f'speech runtime exposes no compatible device; runtime={sidecar_devices!r}')
        chosen = self._device_candidates[0]
        self._selected_device = {
            'workload': 'speech-stt', 'kind': chosen, 'provider': 'OpenVINO',
            'device': chosen, 'model': self.settings.model, 'verified': False,
        }

    def _apply_config(self) -> None:
        if not self._device_candidates:
            return
        errors: list[str] = []
        self._actual_device = None
        for chosen in self._device_candidates:
            self._selected_device = {
                'workload': 'speech-stt', 'kind': chosen, 'provider': 'OpenVINO',
                'device': chosen, 'model': self.settings.model, 'verified': False,
            }
            params = {
                'device': chosen,
                'hotkey': self.settings.hotkey,
                'mode': self.settings.mode,
                'injection_method': self.settings.injection_method,
            'active_app':self._active_app,'privacy_runtime_supported':self._privacy_runtime_supported,'personalization_runtime_supported':self._vocabulary_runtime_supported,
            'context_awareness':self.settings.context_awareness,'dictionary_enabled':self.settings.dictionary_enabled,'default_context_profile':self.settings.default_context_profile,
            }
            try:
                result = self.request('set_config', params, timeout_s=45 if chosen != 'CPU' else 60)
                if isinstance(result, dict):
                    actual = str(result.get('actual_device') or result.get('device') or '').upper()
                    verified = bool(result.get('placement_verified', False))
                    if verified and actual in {'NPU','GPU','CPU'}:
                        # A runtime must not silently claim another class after
                        # we requested an accelerator. A mismatch is a failed
                        # attempt and fallback proceeds to the next class.
                        if actual != chosen:
                            raise RuntimeError(f'placement mismatch: requested {chosen}, runtime verified {actual}')
                        self._actual_device = self.hardware.report_actual(
                            'speech-stt', kind=actual, provider=str(result.get('provider') or 'OpenVINO'),
                            device=str(result.get('device_name') or actual), model=self.settings.model,
                        )
                        self.broker.set_placement(self._model_reservation, actual)
                        return
                errors.append(f'{chosen}: sidecar did not return placement_verified=true after compile/warm-up')
            except Exception as exc:
                errors.append(f'{chosen}: {type(exc).__name__}: {exc}')
                self.bus.emit('speech.device_attempt_failed', 'speech', {'device': chosen, 'error': str(exc)})
                continue
        self.bus.emit('speech.placement.unverified', 'speech', {
            'selected': self._selected_device, 'attempts': errors,
            'reason': 'no sidecar device produced verified placement',
        })
        raise RuntimeError('speech device configuration failed: ' + ' | '.join(errors))

    def _read_loop(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                try: obj = json.loads(line)
                except Exception: continue
                rid = obj.get('id')
                if isinstance(rid, int):
                    with self._lock:
                        self._responses[rid] = obj
                        waiter = self._pending.get(rid)
                    if waiter: waiter.set()
                    continue
                self._handle_event(obj)
        finally:
            self._last_state = 'OFFLINE'
            with self._lock:
                for waiter in self._pending.values(): waiter.set()

    def _emit_final_transcript(self, obj: dict[str, Any], *, status: str = "completed") -> None:
        text = str(obj.get("transcript") or obj.get("text") or "").strip()
        if not text:
            return
        signature = f"{status}:{text}"; now = time.monotonic()
        if signature == self._last_transcript_signature and now - self._last_transcript_at < 2.0:
            return
        self._last_transcript_signature = signature; self._last_transcript_at = now
        self.bus.emit("speech.transcript.final", "speech", {
            "text": text, "raw_text": str(obj.get("raw_text") or ""),
            "app_id": str(obj.get("app_id") or obj.get("application") or ""), "app_name": str(obj.get("app_name") or ""),
            "context_profile": str(obj.get("context_profile") or self.settings.default_context_profile),
            "language": str(obj.get("language") or "en"), "model": self.settings.model, "status": status,
            "duration_ms": obj.get("duration_ms"),
            "error": str(obj.get("detail") or obj.get("error") or "") if status != "completed" else "",
        })

    def refresh_personalization(self) -> dict[str, Any]:
        if not self.running:
            return {"running": False, "dictionary_supported": self._vocabulary_runtime_supported, "count": 0}
        terms=[]
        if self.settings.dictionary_enabled and self.vocabulary_provider is not None:
            try: terms=list(self.vocabulary_provider())[:1000]
            except Exception as exc: self.bus.emit("speech.vocabulary.error","speech",{"error":str(exc)})
        try:
            result=self.request("set_personalization", {
                "dictionary": terms, "context_awareness": bool(self.settings.context_awareness),
                "default_context_profile": self.settings.default_context_profile,
            }, timeout_s=5.0)
            supported=not (isinstance(result,dict) and result.get("supported") is False); self._vocabulary_runtime_supported=bool(supported)
            self.bus.emit("speech.personalization.applied" if supported else "speech.personalization.unsupported","speech",{"dictionary_count":len(terms)})
        except Exception as exc:
            self._vocabulary_runtime_supported=False; self.bus.emit("speech.personalization.unsupported","speech",{"dictionary_count":len(terms),"error":str(exc),"note":"Dictionary remains local; runtime injection requires sidecar support."})
        return {"running": True, "dictionary_supported": self._vocabulary_runtime_supported, "count":len(terms)}

    def _handle_active_app(self, obj: dict[str, Any]) -> None:
        app_id=str(obj.get("app_id") or obj.get("application") or obj.get("process") or "").strip(); app_name=str(obj.get("app_name") or obj.get("title") or "").strip()
        if not app_id: return
        rule=self.app_policy(app_id) if self.app_policy else {"app_id":app_id.lower(),"privacy_action":"allow","context_profile":self.settings.default_context_profile,"matched":False}
        action=str(rule.get("privacy_action") or "allow").lower(); profile=str(rule.get("context_profile") or self.settings.default_context_profile).lower(); paused=bool(self.settings.privacy_pause_enabled and action=="pause"); allow_context=action!="no_context"
        self._active_app={"app_id":app_id,"app_name":app_name,"privacy_action":action,"context_profile":profile,"paused_by_policy":paused,"context_allowed":allow_context,"matched":bool(rule.get("matched",False))}
        self.bus.emit("speech.active_app","speech",dict(self._active_app))
        sig=f"{app_id.lower()}|{paused}|{allow_context}|{profile}"
        if sig==self._privacy_rule_signature:return
        self._privacy_rule_signature=sig
        threading.Thread(target=self._apply_privacy_policy,args=(app_id,paused,allow_context,profile),name="metatron-speech-app-policy",daemon=True).start()

    def _apply_privacy_policy(self, app_id: str, paused: bool, allow_context: bool, profile: str) -> None:
        if self._privacy_runtime_supported is False:return
        try:
            result=self.request("set_app_policy",{"app_id":app_id,"paused":bool(paused),"allow_context":bool(allow_context),"context_profile":profile},timeout_s=3.0)
            supported=not (isinstance(result,dict) and result.get("supported") is False); self._privacy_runtime_supported=bool(supported)
            if not supported: raise RuntimeError("speech sidecar reports app-policy control unsupported")
            self.bus.emit("speech.app_policy.applied","speech",{"app_id":app_id,"paused":paused,"allow_context":allow_context,"context_profile":profile})
        except Exception as exc:
            self._privacy_runtime_supported=False; self.bus.emit("speech.app_policy.unsupported","speech",{"app_id":app_id,"error":str(exc),"note":"Rules remain stored; runtime enforcement requires sidecar support."})

    def _handle_event(self, obj: dict[str, Any]) -> None:
        self._events.append(obj)
        kind = obj.get('event')
        if kind == 'state':
            state = str(obj.get('state') or '').upper(); self._last_state = state
            if state == 'LISTENING': self.presence.user_started()
            elif state == 'TRANSCRIBING': self.presence.asr_started()
            elif state in {'READY','IDLE','INJECTED','NOSPEECH'}:
                self.presence.user_stopped()
                if state == 'INJECTED': self._emit_final_transcript(obj,status='completed')
            elif state == 'INJECTION_BLOCKED':
                self.presence.user_stopped()
                self.presence.signal('warning', str(obj.get('detail') or 'Text injection was blocked by Windows integrity/UIPI policy'), source='speech')
                self._emit_final_transcript(obj,status='injection_blocked')
                self.bus.emit('speech.injection.blocked', 'speech', {'detail':str(obj.get('detail') or ''),'transcript':str(obj.get('transcript') or ''),'method':self.settings.injection_method})
            elif state == 'ERROR': self.presence.signal('error', str(obj.get('detail') or 'Speech engine error'), source='speech')
            self.bus.emit('speech.state', 'speech', {'state': state, 'detail': obj.get('detail','')})
        elif kind == 'transcript':
            if bool(obj.get('final',True)): self._emit_final_transcript(obj,status=str(obj.get('status') or 'completed'))
            else: self.presence.asr_partial(str(obj.get('text') or obj.get('transcript') or ''))
        elif kind == 'active_app':
            self._handle_active_app(obj)
        elif kind == 'placement':
            actual = str(obj.get('device') or '').upper()
            if bool(obj.get('verified', False)) and actual in {'NPU','GPU','CPU'}:
                self._actual_device = self.hardware.report_actual(
                    'speech-stt', kind=actual, provider=str(obj.get('provider') or 'OpenVINO'),
                    device=str(obj.get('device_name') or actual), model=self.settings.model,
                )
                self.bus.emit('speech.placement.verified', 'speech', dict(self._actual_device))
        elif kind == 'level':
            value = max(0.0, min(1.0, float(obj.get('value', 0.0))))
            self.presence.user_level(value)
            self.bus.emit_ephemeral('speech.user.level', 'speech', {'level': value})
        else:
            self.bus.emit_ephemeral('speech.runtime.event', 'speech', obj)

    def request(self, cmd: str, params: dict[str, Any] | None = None, timeout_s: float = 30.0) -> Any:
        if not self.running or not self._proc or not self._proc.stdin:
            raise RuntimeError('speech runtime is not running')
        with self._lock:
            rid = self._next_id; self._next_id += 1
            waiter = threading.Event(); self._pending[rid] = waiter
            self._proc.stdin.write(json.dumps({'id': rid, 'cmd': cmd, 'params': params or {}}, separators=(',',':'))+'\n')
            self._proc.stdin.flush()
        if not waiter.wait(timeout_s):
            with self._lock: self._pending.pop(rid, None); self._responses.pop(rid, None)
            raise TimeoutError(f'speech runtime timeout: {cmd}')
        with self._lock:
            self._pending.pop(rid, None); response = self._responses.pop(rid, None)
        if response is None:
            raise RuntimeError('speech runtime exited')
        if not response.get('ok', False):
            err = response.get('error') or {}; raise RuntimeError(str(err.get('message') or 'speech runtime error'))
        return response.get('result')

    def stop(self) -> dict[str, Any]:
        with self._lock:
            proc = self._proc; self._proc = None
        if proc:
            if proc.poll() is None:
                try:
                    if proc.stdin: proc.stdin.write(json.dumps({'id': 0, 'cmd':'shutdown','params':{}})+'\n'); proc.stdin.flush()
                    proc.wait(timeout=4)
                except Exception:
                    proc.terminate()
                    try: proc.wait(timeout=2)
                    except Exception: proc.kill()
            for pipe in (proc.stdin, proc.stdout):
                try:
                    if pipe and not pipe.closed: pipe.close()
                except Exception: pass
        if self._reader and self._reader.is_alive(): self._reader.join(timeout=1)
        self._reader = None
        if self._job is not None:
            self._job.close(); self._job = None
        if self._stderr:
            try: self._stderr.close()
            except Exception: pass
            self._stderr = None
        try: self.broker.unload(self._model_reservation)
        except Exception: pass
        self._selected_device = None; self._device_candidates = []; self._actual_device = None; self._last_state = 'OFFLINE'
        self._active_app=None; self._privacy_runtime_supported=None; self._privacy_rule_signature=''; self._vocabulary_runtime_supported=None
        self.bus.emit('speech.runtime.stopped', 'speech', {})
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            'enabled': self.settings.enabled, 'configured': self.configured,
            'running': self.running, 'pid': self.pid, 'state': self._last_state,
            'model': self.settings.model, 'selected_device': self._selected_device, 'device_candidates': list(self._device_candidates), 'actual_device': self._actual_device,
            'device_order': list(self.settings.device_order), 'cleanup_enabled': self.settings.cleanup_enabled,
            'hotkey': self.settings.hotkey, 'mode': self.settings.mode,
            'injection_method': self.settings.injection_method,
            'active_app':self._active_app,'privacy_runtime_supported':self._privacy_runtime_supported,'personalization_runtime_supported':self._vocabulary_runtime_supported,
            'context_awareness':self.settings.context_awareness,'dictionary_enabled':self.settings.dictionary_enabled,'default_context_profile':self.settings.default_context_profile,
        }

    def events(self, clear: bool = False) -> list[dict[str, Any]]:
        out = list(self._events)
        if clear: self._events.clear()
        return out

    def close(self) -> None:
        self.stop()


def speech_command_from_env() -> list[str]:
    return _split_command(os.environ.get('METATRON_SPEECH_CMD',''))
