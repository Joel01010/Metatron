"""Disposable test-only cleanup worker for contention/transport benchmarking.

It intentionally performs deterministic text cleanup and optional memory/CPU
pressure. It is NOT S1-mini and can never be selected as the production model.
"""
from __future__ import annotations
import argparse, json, re, sys, time


def clean(s: str) -> str:
    s = re.sub(r'\b(?:um|uh|erm|hmm)\b[, ]*', '', s, flags=re.I).strip()
    s = re.sub(r'\s+', ' ', s)
    if not s: return ''
    s = s[0].upper() + s[1:]
    if not s.endswith(('.', '?', '!')): s += '.'
    return s


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--reserve-mib',type=int,default=0); ap.add_argument('--delay-ms',type=float,default=0)
    a=ap.parse_args(); reserve=bytearray(max(0,a.reserve_mib)*1024*1024)
    for line in sys.stdin:
        try:
            req=json.loads(line); rid=req.get('id'); cmd=req.get('cmd'); p=req.get('params') or {}
            if cmd=='cleanup':
                if a.delay_ms: time.sleep(a.delay_ms/1000)
                out={'id':rid,'ok':True,'result':clean(str(p.get('text') or ''))}
            elif cmd=='shutdown':
                print(json.dumps({'id':rid,'ok':True,'result':True}),flush=True); return
            else: out={'id':rid,'ok':False,'error':{'message':'unknown command'}}
        except Exception as e: out={'id':None,'ok':False,'error':{'message':str(e)}}
        print(json.dumps(out,separators=(',',':')),flush=True)
if __name__=='__main__': main()
