from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any

from .events import EventBus


@dataclass(slots=True)
class AudioFocusState:
    tts_active: bool = False
    capture_suppressed: bool = False
    suppress_until: float = 0.0
    generation: int = 0


class AudioFocusController:
    """Tiny full-duplex/echo-guard controller.

    Metatron cannot assume the speaker path is acoustically isolated from the
    microphone. While TTS plays, capture is suppressed by default and is
    released after a short tail so the assistant does not transcribe itself.
    The UI/STT host can opt into barge-in by calling ``user_barge_in()``.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        suppress_during_tts: bool = True,
        tail_ms: int = 280,
        barge_in: bool = True,
    ) -> None:
        self.bus = bus
        self.suppress_during_tts = bool(suppress_during_tts)
        self.tail_ms = max(0, min(2000, int(tail_ms)))
        self.barge_in = bool(barge_in)
        self._s = AudioFocusState()
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                **asdict(self._s),
                "suppress_during_tts": self.suppress_during_tts,
                "tail_ms": self.tail_ms,
                "barge_in": self.barge_in,
                "capture_allowed": not self._s.capture_suppressed,
            }

    def _cancel_timer(self) -> None:
        timer = self._timer
        self._timer = None
        if timer is not None:
            timer.cancel()

    def tts_started(self) -> dict[str, Any]:
        with self._lock:
            self._cancel_timer()
            self._s.generation += 1
            self._s.tts_active = True
            if self.suppress_during_tts:
                self._s.capture_suppressed = True
                self._s.suppress_until = float("inf")
            st = self.status()
        if self.suppress_during_tts:
            self.bus.emit("speech.capture.suspended", "audio-focus", {
                "reason": "tts", "generation": st["generation"]
            })
        return st

    def tts_finished(self) -> dict[str, Any]:
        with self._lock:
            self._s.tts_active = False
            generation = self._s.generation
            if not self._s.capture_suppressed:
                return self.status()
            delay = self.tail_ms / 1000.0
            self._s.suppress_until = time.monotonic() + delay
            self._cancel_timer()
            if delay <= 0:
                return self._resume(generation)
            timer = threading.Timer(delay, self._resume, args=(generation,))
            timer.daemon = True
            self._timer = timer
            timer.start()
            return self.status()

    def _resume(self, generation: int) -> dict[str, Any]:
        with self._lock:
            if generation != self._s.generation or self._s.tts_active:
                return self.status()
            self._s.capture_suppressed = False
            self._s.suppress_until = 0.0
            self._timer = None
            st = self.status()
        self.bus.emit("speech.capture.resumed", "audio-focus", {
            "reason": "tts-tail-complete", "generation": generation
        })
        return st

    def user_barge_in(self) -> dict[str, Any]:
        """Release capture immediately when the host explicitly detects a user.

        The TTS manager is responsible for stopping playback when it receives a
        barge-in command. Keeping that decision outside this controller avoids a
        circular dependency.
        """
        if not self.barge_in:
            return self.status()
        with self._lock:
            self._cancel_timer()
            self._s.generation += 1
            self._s.tts_active = False
            self._s.capture_suppressed = False
            self._s.suppress_until = 0.0
            st = self.status()
        self.bus.emit("speech.capture.resumed", "audio-focus", {
            "reason": "barge-in", "generation": st["generation"]
        })
        return st

    def close(self) -> None:
        with self._lock:
            self._cancel_timer()
