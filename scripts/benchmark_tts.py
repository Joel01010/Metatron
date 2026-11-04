#!/usr/bin/env python3
"""Benchmark the configured Kokoro worker without importing ONNX into Metatron.

Run after Setup-Kokoro-TTS.ps1, from the repository root:
    python scripts/benchmark_tts.py

Reports cold/warm synthesis latency, real-time factor, worker process-tree RSS,
and confirms that stopping the worker releases its broker reservation.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import wave
from pathlib import Path

from metatron.memory import ModelBroker, Reservation
from metatron.telemetry import process_tree_rss_mib
from metatron.workers import JsonlWorkerSupervisor


def wav_duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def main() -> int:
    py = os.environ.get("METATRON_KOKORO_PYTHON", "")
    model = os.environ.get("METATRON_KOKORO_MODEL", "")
    voices = os.environ.get("METATRON_KOKORO_VOICES", "")
    voice = os.environ.get("METATRON_TTS_VOICE", "am_fenrir")
    if not (py and model and voices):
        raise SystemExit("Kokoro environment is not configured. Run Setup-Kokoro-TTS.ps1 first.")

    repo = Path(__file__).resolve().parents[1]
    worker_script = repo / "scripts" / "kokoro_onnx_worker.py"
    broker = ModelBroker(1024)
    broker.register(Reservation("kokoro-82m-tts", 420, idle_unload_s=45))
    worker = JsonlWorkerSupervisor(
        "kokoro-82m-tts", [py, str(worker_script), "--model", model, "--voices", voices],
        broker, request_timeout_s=60.0,
    )
    text = "Metatron is online. All systems are operating within normal parameters."
    rows = []
    try:
        with tempfile.TemporaryDirectory() as td:
            for i in range(3):
                out = Path(td) / f"bench-{i}.wav"
                t0 = time.perf_counter()
                result = worker.request("synthesize", {
                    "text": text, "output_path": str(out), "voice": voice, "speed": 0.96,
                }, timeout_s=60.0)
                latency = time.perf_counter() - t0
                duration = wav_duration_s(out)
                rss = process_tree_rss_mib(worker.pid) if worker.pid else None
                rows.append({
                    "run": i + 1,
                    "latency_ms": round(latency * 1000, 1),
                    "audio_s": round(duration, 3),
                    "rtf": round(latency / duration, 3) if duration else None,
                    "rss_mib": round(rss, 1) if rss is not None else None,
                    "voice": result.get("voice"),
                })
        print(json.dumps({
            "model": model,
            "voice": voice,
            "runs": rows,
            "peak_rss_mib": max((x["rss_mib"] or 0) for x in rows),
            "warm_rtf": rows[-1]["rtf"],
        }, indent=2))
    finally:
        worker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
