#!/usr/bin/env python3
"""Disposable JSONL worker for Kokoro-ONNX.

Optional runtime dependencies (kept out of Metatron core):
    kokoro-onnx
    soundfile

The worker loads Kokoro once, serves small synthesis requests, and is killed by
Metatron's memory governor after idle. That gives premium local TTS without a
permanently resident Python/ONNX process.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def reply(rid, ok, result=None, message=""):
    obj = {"id": rid, "ok": bool(ok)}
    if ok:
        obj["result"] = result
    else:
        obj["error"] = {"message": message or "worker error"}
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--voices", required=True)
    args = ap.parse_args()

    init_error = ""
    tts = None
    sf = None
    try:
        from kokoro_onnx import Kokoro
        import soundfile as _sf
        sf = _sf
        tts = Kokoro(args.model, args.voices)
    except Exception as exc:
        init_error = f"Kokoro init failed: {type(exc).__name__}: {exc}"

    try:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            rid = None
            try:
                req = json.loads(raw)
                rid = req.get("id")
                cmd = req.get("cmd")
                p = req.get("params") or {}
                if init_error:
                    reply(rid, False, message=init_error)
                    continue
                if cmd == "ping":
                    reply(rid, True, {"ready": True})
                    continue
                if cmd != "synthesize":
                    reply(rid, False, message=f"unknown command {cmd!r}")
                    continue
                text = str(p.get("text") or "").strip()
                if not text:
                    reply(rid, False, message="empty text")
                    continue
                output = Path(str(p["output_path"]))
                output.parent.mkdir(parents=True, exist_ok=True)
                voice = str(p.get("voice") or "am_fenrir")
                speed = max(0.7, min(1.3, float(p.get("speed", 0.96))))
                audio, sample_rate = tts.create(
                    text, voice=voice, speed=speed, lang="en-us"
                )
                sf.write(str(output), audio, sample_rate, subtype="PCM_16")
                reply(rid, True, {
                    "path": str(output),
                    "sample_rate": int(sample_rate),
                    "voice": voice,
                    "speed": speed,
                })
            except Exception as exc:
                reply(rid, False, message=f"{type(exc).__name__}: {exc}")
    finally:
        try:
            if tts is not None and getattr(tts, "voices", None) is not None:
                tts.voices.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
