#!/usr/bin/env python3
"""Windows microphone/audio endpoint smoke test using python-sounddevice (MIT).

Captures a short block from the default input device and reports RMS/peak. It
never writes audio to disk. This verifies that a capture endpoint can actually
be opened and sampled; it is not a speech-recognition accuracy test.
"""
from __future__ import annotations
import argparse, json, math, platform, sys, time
from pathlib import Path


def emit(path: str, obj: dict) -> None:
    if path:
        p=Path(path); p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(obj,indent=2))


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--seconds',type=float,default=1.5); ap.add_argument('--samplerate',type=int,default=16000); ap.add_argument('--json-out',default=''); a=ap.parse_args()
    if platform.system() != 'Windows':
        out={'schema':1,'version':'1.4.0','status':'SKIP','reason':'Windows-only audio qualification'};emit(a.json_out,out);return 3
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as exc:
        out={'schema':1,'version':'1.4.0','status':'SKIP','reason':f'sounddevice unavailable: {type(exc).__name__}: {exc}'};emit(a.json_out,out);return 3
    try:
        default_in, default_out = sd.default.device
        devices = sd.query_devices()
        info = sd.query_devices(default_in, 'input')
        frames=max(1,int(a.seconds*a.samplerate))
        t0=time.perf_counter(); audio=sd.rec(frames,samplerate=a.samplerate,channels=1,dtype='float32',blocking=True); elapsed=time.perf_counter()-t0
        samples=np.asarray(audio,dtype=np.float32).reshape(-1)
        rms=float(math.sqrt(float(np.mean(samples*samples)))) if samples.size else 0.0
        peak=float(np.max(np.abs(samples))) if samples.size else 0.0
        out={'schema':1,'version':'1.4.0','status':'PASS','default_input_index':int(default_in),'default_output_index':int(default_out),'input_name':str(info.get('name','')),'sample_rate':a.samplerate,'frames':int(samples.size),'capture_elapsed_ms':round(elapsed*1000,2),'rms':rms,'peak':peak,'non_silent':bool(peak>1e-5),'device_count':len(devices)}
        emit(a.json_out,out);return 0
    except Exception as exc:
        out={'schema':1,'version':'1.4.0','status':'FAIL','error':f'{type(exc).__name__}: {exc}'};emit(a.json_out,out);return 2
if __name__=='__main__':raise SystemExit(main())
