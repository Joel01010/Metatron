#!/usr/bin/env python3
"""Repeatable control-plane benchmark with JSON output.

This is intentionally accelerator-independent. Windows certification adds GPU,
NPU and PDH counters using Collect-WindowsMetrics.ps1 around the same run.
"""
from __future__ import annotations
import argparse, json, os, platform, statistics, subprocess, sys, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from metatron.benchmark import PROVISIONAL_GATES
from metatron.telemetry import process_rss_mib, process_tree_rss_mib, system_memory


def pct(xs,p):
    if not xs:return None
    ys=sorted(xs); return ys[min(len(ys)-1,max(0,round((len(ys)-1)*p)))]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--samples',type=int,default=50); ap.add_argument('--json-out',default='')
    a=ap.parse_args()
    env=os.environ.copy(); td=tempfile.TemporaryDirectory(); env['METATRON_DATA_DIR']=td.name; env['PYTHONPATH']=str(ROOT)
    t0=time.perf_counter()
    p=subprocess.Popen([sys.executable,'-X','utf8','-m','metatron.main'],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',bufsize=1)
    spawn_call_ms=(time.perf_counter()-t0)*1000
    lat=[]
    try:
        # Readiness is the first successful protocol response, not Popen() return.
        ready_req={'id':0,'cmd':'status','params':{}}
        p.stdin.write(json.dumps(ready_req,separators=(',',':'))+'\n'); p.stdin.flush()
        while True:
            line=p.stdout.readline()
            if not line: raise RuntimeError('backend exited before ready')
            obj=json.loads(line)
            if obj.get('id')==0:
                if not obj.get('ok'): raise RuntimeError(str(obj.get('error')))
                break
        ready_ms=(time.perf_counter()-t0)*1000
        for i in range(a.samples):
            req={'id':i+1,'cmd':'status','params':{}}
            st=time.perf_counter(); p.stdin.write(json.dumps(req,separators=(',',':'))+'\n'); p.stdin.flush()
            while True:
                line=p.stdout.readline()
                if not line: raise RuntimeError('backend exited')
                obj=json.loads(line)
                if obj.get('id')==i+1:
                    if not obj.get('ok'): raise RuntimeError(str(obj.get('error')))
                    break
            lat.append((time.perf_counter()-st)*1000)
        tree=process_tree_rss_mib(p.pid)
        result={
          'schema':1,'platform':platform.platform(),'python':sys.version.split()[0],
          'backend_spawn_call_ms':spawn_call_ms,'backend_ready_ms':ready_ms,'command_p50_ms':statistics.median(lat),'command_p95_ms':pct(lat,.95),
          'backend_process_tree_working_set_mib':tree,'harness_working_set_mib':process_rss_mib(),
          'system_memory':system_memory(),'provisional_gates':PROVISIONAL_GATES,
          'passes_bridge_p95':pct(lat,.95) <= PROVISIONAL_GATES['bridge_p95_ms_max'],
        }
        text=json.dumps(result,indent=2); print(text)
        if a.json_out: Path(a.json_out).write_text(text+'\n',encoding='utf-8')
        return 0 if result['passes_bridge_p95'] else 2
    finally:
        try:
            p.stdin.write(json.dumps({'id':999999,'cmd':'shutdown','params':{}})+'\n'); p.stdin.flush(); p.wait(timeout=3)
        except Exception:
            p.kill(); p.wait(timeout=2)
        td.cleanup()

if __name__=='__main__': raise SystemExit(main())
