#!/usr/bin/env python3
"""Benchmark a disposable Metatron cleanup worker.

Worker protocol:
  stdin:  {"id":1,"cmd":"cleanup","params":{"text":"..."}}
  stdout: {"id":1,"ok":true,"result":"cleaned text"}

Example once the OpenVINO worker exists:
  python scripts/benchmark_cleanup_worker.py --max-rss-mib 650 -- \
      python s1_openvino_worker.py --device GPU

The harness itself has no ML dependencies. It records cold start, per-request
latency, correctness on a compact English smoke set, and process-tree RSS.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from metatron.telemetry import process_tree_rss_mib

CASES = [
    ("um send the report by friday", "Send the report by Friday."),
    ("i think the answer is forty two no sorry forty three", "I think the answer is 43."),
    ("send it to support at superwhisper dot com", "Send it to support@superwhisper.com."),
    ("um", ""),
]


def percentile(values, p):
    if not values: return 0.0
    v=sorted(values); idx=min(len(v)-1, max(0, int(round((len(v)-1)*p))))
    return v[idx]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-rss-mib', type=float, default=650)
    ap.add_argument('--max-p95-ms', type=float, default=750)
    ap.add_argument('--json-out')
    ap.add_argument('command', nargs=argparse.REMAINDER)
    ns=ap.parse_args()
    cmd=ns.command[1:] if ns.command[:1]==['--'] else ns.command
    if not cmd: ap.error('worker command required after --')
    t0=time.perf_counter()
    p=subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                       text=True, encoding='utf-8', bufsize=1)
    lat=[]; peak=0.0; rows=[]
    try:
        for i,(raw,expected) in enumerate(CASES,1):
            req={'id':i,'cmd':'cleanup','params':{'text':raw,'styling':'semi-formal','structure':'prose','context':'general'}}
            st=time.perf_counter(); p.stdin.write(json.dumps(req,separators=(',',':'))+'\n'); p.stdin.flush()
            line=p.stdout.readline()
            elapsed=(time.perf_counter()-st)*1000; lat.append(elapsed)
            rss=process_tree_rss_mib(p.pid) or 0.0; peak=max(peak,rss)
            obj=json.loads(line); actual=str(obj.get('result','')) if obj.get('ok') else ''
            rows.append({'input':raw,'expected':expected,'actual':actual,'ok':actual==expected,'latency_ms':elapsed})
        result={
            'command':cmd,
            'cold_plus_first_ms':lat[0] if lat else None,
            'latency_p50_ms':statistics.median(lat) if lat else None,
            'latency_p95_ms':percentile(lat,.95),
            'peak_process_tree_rss_mib':peak,
            'correct':sum(r['ok'] for r in rows),
            'total':len(rows),
            'within_rss_budget':peak <= ns.max_rss_mib,
            'within_latency_budget':percentile(lat,.95) <= ns.max_p95_ms,
            'cases':rows,
        }
        text=json.dumps(result,indent=2)
        print(text)
        if ns.json_out: Path(ns.json_out).write_text(text+'\n',encoding='utf-8')
        return 0 if result['correct']==result['total'] and result['within_rss_budget'] and result['within_latency_budget'] else 2
    finally:
        if p.poll() is None:
            p.terminate()
            try: p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill(); p.wait(timeout=1)

if __name__=='__main__': raise SystemExit(main())
