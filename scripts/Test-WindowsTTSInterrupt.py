#!/usr/bin/env python3
from __future__ import annotations
import json
import platform
import tempfile
import time
import wave
from pathlib import Path

MAX_STOP_LATENCY_MS = 2000.0


def main() -> int:
    if platform.system() != "Windows":
        print(json.dumps({"schema": 2, "version": "1.4.0", "status": "SKIP", "reason": "Windows-only"}))
        return 3
    try:
        import winsound
        from metatron.memory import ModelBroker, Reservation
        from metatron.tts import WindowsSapiProvider
    except Exception as exc:
        print(json.dumps({"schema": 2, "version": "1.4.0", "status": "FAIL", "error": str(exc)}))
        return 2

    broker = ModelBroker(256)
    broker.register(Reservation("windows-sapi-tts", 64))
    provider = WindowsSapiProvider(broker)
    if not provider.available():
        print(json.dumps({"schema": 2, "version": "1.4.0", "status": "SKIP", "reason": "Windows SAPI unavailable"}))
        return 3

    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "interrupt.wav"
        provider.synthesize(
            "This is a deliberately long Metatron speech interruption verification sentence. " * 8,
            wav_path,
            "",
            1.0,
        )
        with wave.open(str(wav_path), "rb") as wav_file:
            duration_s = wav_file.getnframes() / wav_file.getframerate()

        test_started = time.perf_counter()
        winsound.PlaySound(
            str(wav_path),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
        time.sleep(0.30)
        stop_started = time.perf_counter()
        winsound.PlaySound(None, 0)
        stop_ms = (time.perf_counter() - stop_started) * 1000.0
        total_ms = (time.perf_counter() - test_started) * 1000.0

        # A valid interruption must return quickly and, crucially, the test must
        # finish far before the generated clip would naturally end. The previous
        # synchronous test could report PASS after waiting ~45 seconds.
        interrupted_early = total_ms < min(duration_s * 500.0, 2500.0)
        passed = duration_s > 2.0 and stop_ms < MAX_STOP_LATENCY_MS and interrupted_early
        out = {
            "schema": 2,
            "version": "1.4.0",
            "status": "PASS" if passed else "FAIL",
            "wav_duration_s": round(duration_s, 3),
            "stop_latency_ms": round(stop_ms, 2),
            "test_elapsed_ms": round(total_ms, 2),
            "max_stop_latency_ms": MAX_STOP_LATENCY_MS,
            "interrupted_before_natural_end": interrupted_early,
        }
        print(json.dumps(out, indent=2))
        return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
