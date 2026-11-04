from __future__ import annotations

import math
import struct
import wave
from pathlib import Path
from typing import Any


def _pcm_rms(data: bytes, sample_width: int) -> float:
    if not data:
        return 0.0
    if sample_width == 1:
        vals = (b - 128 for b in data)
        max_amp = 127.0
        total = count = 0
        for v in vals:
            total += v * v; count += 1
        return math.sqrt(total / max(1, count)) / max_amp
    if sample_width == 2:
        count = len(data) // 2
        if count <= 0:
            return 0.0
        vals = struct.unpack(f"<{count}h", data[:count * 2])
        total = sum(v * v for v in vals)
        return math.sqrt(total / count) / 32767.0
    if sample_width == 3:
        count = len(data) // 3
        if count <= 0:
            return 0.0
        total = 0
        for i in range(0, count * 3, 3):
            raw = int.from_bytes(data[i:i+3], "little", signed=False)
            if raw & 0x800000:
                raw -= 1 << 24
            total += raw * raw
        return math.sqrt(total / count) / 8388607.0
    if sample_width == 4:
        count = len(data) // 4
        if count <= 0:
            return 0.0
        vals = struct.unpack(f"<{count}i", data[:count * 4])
        total = sum(v * v for v in vals)
        return math.sqrt(total / count) / 2147483647.0
    raise ValueError(f"unsupported PCM sample width: {sample_width}")


def wav_envelope(path: str | Path, hz: int = 30, max_points: int = 1200) -> dict[str, Any]:
    """Extract a compact normalized RMS envelope from a PCM WAV file.

    It is intentionally stdlib-only. The envelope is used by the orb renderer,
    not for audio analysis/recognition, so 20-30 Hz is ample and keeps IPC small.
    """
    p = Path(path)
    with wave.open(str(p), "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        width = wf.getsampwidth()
        frames = wf.getnframes()
        if rate <= 0 or frames < 0:
            raise ValueError("invalid WAV metadata")
        duration_s = frames / rate if rate else 0.0
        target_hz = max(5, min(int(hz), 60))
        if duration_s > 0 and duration_s * target_hz > max_points:
            target_hz = max(5, int(max_points / duration_s))
        frames_per_bin = max(1, int(rate / target_hz))
        levels: list[dict[str, float]] = []
        idx = 0
        peak = 0.0
        while True:
            chunk = wf.readframes(frames_per_bin)
            if not chunk:
                break
            level = max(0.0, min(1.0, _pcm_rms(chunk, width)))
            peak = max(peak, level)
            levels.append({"t_ms": idx * frames_per_bin / rate * 1000.0, "raw": level})
            idx += 1

    # Normalize per utterance but retain a floor so whispers don't look like
    # explosions. sqrt compression gives a pleasing speaking response.
    denom = max(peak, 0.08)
    out: list[dict[str, float]] = []
    for x in levels:
        normalized = min(1.0, float(x["raw"]) / denom)
        out.append({"t_ms": round(float(x["t_ms"]), 1), "level": round(math.sqrt(normalized), 4)})
    return {
        "path": str(p),
        "duration_ms": round(duration_s * 1000.0, 1),
        "sample_rate": rate,
        "channels": channels,
        "sample_width": width,
        "hz": target_hz,
        "levels": out,
    }
