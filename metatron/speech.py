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
from typing import Any

from .hardware import HardwareManager
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
    _proc: subprocess.Popen | None = field(default=None, init=False, repr=False)
    _reader: threading.Thread | None = field(default=None, init=False, repr=False)
    _stderr: Any = field(default=None, init=False, repr=False)
    _next_id: int = field(default=1, init=False, repr=False)
    _pending: dict[int, threading.Event] = field(default_factory=dict, init=False, repr=False)
    _responses: dict[int, dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _events: collections.deque = field(default_factory=lambda: collections.deque(maxlen=512), init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _actual_device: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _last_state: str = field(default='OFFLINE', init=False, repr=False)
    _model_reservation: str = field(default='parakeet-unified-en-0.6b', init=False, repr=False)

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
                    creationflags=flags,
                )
            except Exception:
                self.broker.unload(self._model_reservation)
                raise
            self._reader = threading.Thread(target=self._read_loop, name='metatron-speech', daemon=True)
            self._reader.start()
        # Most compatible engines answer ping and list_ov_devices.  Configure
        # only after protocol startup so fallback is explicit and observable.
        self.request('ping', {}, timeout_s=10)
        self._configure_best_device()
        self._apply_config()
        self.bus.emit('speech.runtime.started', 'speech', {'pid': self.pid, 'device': self._actual_device})
        return self.status()

    def _configure_best_device(self) -> None:
        sidecar_devices: list[str] = []
        try:
            result = self.request('list_ov_devices', {}, timeout_s=10) or {}
            sidecar_devices = [str(x).upper() for x in result.get('devices', [])]
        except Exception:
            pass
        desired = [str(x).upper() for x in self.settings.device_order]
        chosen: str | None = None
        for kind in desired:
            if kind in sidecar_devices:
                chosen = kind; break
        if chosen is None:
            # The generic hardware layer may know about providers that this
            # model runtime does not.  Never call that an actual placement.
            selected = self.hardware.select('speech-stt', desired)
            if selected and selected.get('kind') in sidecar_devices:
                chosen = str(selected['kind'])
        if chosen is None and 'CPU' in sidecar_devices:
            chosen = 'CPU'
        if chosen is None:
            raise RuntimeError(f'speech runtime exposes no compatible device; runtime={sidecar_devices!r}')
        self._actual_device = self.hardware.report_actual(
            'speech-stt', kind=chosen, provider='OpenVINO', device=chosen, model=self.settings.model,
        )

    def _apply_config(self) -> None:
        if not self._actual_device:
            return
        params = {
            'device': self._actual_device['kind'],
            'hotkey': self.settings.hotkey,
            'mode': self.settings.mode,
            'injection_method': self.settings.injection_method,
        }
        try:
            self.request('set_config', params, timeout_s=180)
        except Exception as exc:
            # Some sidecars expose only a subset. Device placement is the hard
            # requirement; cosmetic config failure should remain diagnosable.
            self.bus.emit('speech.config.warning', 'speech', {'error': str(exc), 'params': params})

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

    def _handle_event(self, obj: dict[str, Any]) -> None:
        self._events.append(obj)
        kind = obj.get('event')
        if kind == 'state':
            state = str(obj.get('state') or '').upper(); self._last_state = state
            if state == 'LISTENING': self.presence.user_started()
            elif state == 'TRANSCRIBING': self.presence.asr_started()
            elif state in {'READY','IDLE','INJECTED','NOSPEECH'}: self.presence.user_stopped()
            elif state == 'ERROR': self.presence.signal('error', str(obj.get('detail') or 'Speech engine error'), source='speech')
            self.bus.emit('speech.state', 'speech', {'state': state, 'detail': obj.get('detail','')})
        elif kind == 'level':
            value = max(0.0, min(1.0, float(obj.get('value', 0.0))))
            self.presence.user_level(value)
            self.bus.emit_live('speech.user.level', 'speech', {'level': value})
        else:
            self.bus.emit_live('speech.runtime.event', 'speech', obj)

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
        if self._stderr:
            try: self._stderr.close()
            except Exception: pass
            self._stderr = None
        try: self.broker.unload(self._model_reservation)
        except Exception: pass
        self._actual_device = None; self._last_state = 'OFFLINE'
        self.bus.emit('speech.runtime.stopped', 'speech', {})
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            'enabled': self.settings.enabled, 'configured': self.configured,
            'running': self.running, 'pid': self.pid, 'state': self._last_state,
            'model': self.settings.model, 'actual_device': self._actual_device,
            'device_order': list(self.settings.device_order), 'cleanup_enabled': self.settings.cleanup_enabled,
            'hotkey': self.settings.hotkey, 'mode': self.settings.mode,
            'injection_method': self.settings.injection_method,
        }

    def events(self, clear: bool = False) -> list[dict[str, Any]]:
        out = list(self._events)
        if clear: self._events.clear()
        return out

    def close(self) -> None:
        self.stop()


def speech_command_from_env() -> list[str]:
    return _split_command(os.environ.get('METATRON_SPEECH_CMD',''))
