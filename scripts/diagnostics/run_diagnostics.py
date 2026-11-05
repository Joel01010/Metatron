#!/usr/bin/env python3
"""Reproducible diagnostics suite; bounded subprocesses, clear SKIP/FAIL semantics.
Offline by default. No package installation, uploads, database reads or code changes.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/'scripts'


def run_step(name,command,cwd,out,timeout=180,env=None):
    slug=''.join(c if c.isalnum() or c in '-_' else '-' for c in name.lower())
    stdout=out/(slug+'.stdout.txt')
    stderr=out/(slug+'.stderr.txt')
    started=time.monotonic()
    result={'name':name,'command_label':name + ' (arguments omitted from shareable summary)',
            'duration_s':None,'status':None,'exit_code':None,'stdout':stdout.name,'stderr':stderr.name}
    with stdout.open('w',encoding='utf-8') as o,stderr.open('w',encoding='utf-8') as e:
        try:
            cp=subprocess.run(command,cwd=cwd,env=env,stdout=o,stderr=e,timeout=timeout,check=False)
            result['exit_code']=cp.returncode
            result['status']='PASS' if cp.returncode==0 else 'FAIL'
        except subprocess.TimeoutExpired:
            result['status']='TIMEOUT'
        except OSError as exc:
            result['status']='ERROR'
            e.write(str(exc)+'\n')
    result['duration_s']=round(time.monotonic()-started,3)
    return result


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def bundle(directory,path):
    allowed={'environment.json','diagnostic-summary.json','product-audit.json','core-benchmark.json','process-analysis.json','windows-metrics-analysis.json'}
    items=sorted(x for x in directory.iterdir() if x.is_file() and x.name in allowed)
    inventory=[{'path':str(x.relative_to(directory)).replace('\\','/'),'bytes':x.stat().st_size,'sha256':sha256(x)} for x in items]
    manifest=directory/'manifest.json'
    manifest.write_text(json.dumps({'schema':1,'files':inventory},indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for item in items+[manifest]:z.write(item,item.relative_to(directory))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--timeout',type=int,default=180)
    ap.add_argument('--pid',type=int,help='Existing Metatron desktop/backend PID for process-tree sampling')
    ap.add_argument('--sample-seconds',type=int,default=30)
    ap.add_argument('--skip-tests',action='store_true')
    ap.add_argument('--skip-benchmark',action='store_true')
    ap.add_argument('--with-cargo',action='store_true',help='Run cargo check if installed; may require internet/cached crates')
    ap.add_argument('--make-bundle',action='store_true')
    a=ap.parse_args()
    if not 10 <= a.timeout <= 3600 or not 2 <= a.sample_seconds <= 86400:ap.error('invalid time bounds')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Deliberately no host name, username, network address, exact OS user path or env dump.
    info={'schema':1,'started_utc':datetime.now(timezone.utc).isoformat(),'platform':platform.system(),
          'python_version':platform.python_version(),'architecture':platform.machine(),
          'privacy':'Outputs are local; inspect logs before sharing because external test programs may print paths. Bundle excludes command stdout/stderr.',
          'metrics_not_provided_here':['Windows system commit','GPU engine/VRAM','NPU placement proof']}
    (out/'environment.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    steps=[]
    env=dict(os.environ)
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    env['PYTHONDONTWRITEBYTECODE']='1'
    if not a.skip_tests:
        steps.append(run_step('pytest',[sys.executable,'-W','error','-m','pytest','-q'],ROOT,out,a.timeout,env))
        steps.append(run_step('compileall',[sys.executable,'-m','compileall','-q',str(ROOT/'metatron'),str(ROOT/'scripts'),str(ROOT/'tests')],ROOT,out,a.timeout,env))
        steps.append(run_step('product_audit',[sys.executable,str(SCRIPTS/'product_audit.py'),'--json-out',str(out/'product-audit.json')],ROOT,out,a.timeout,env))
        node=shutil.which('node')
        for name in ('app','orb','orb-renderer'):
            if node:steps.append(run_step('node_'+name,[node,'--check',str(ROOT/'ui'/(name+'.js'))],ROOT,out,a.timeout,env))
            else:steps.append({'name':'node_'+name,'status':'SKIP','reason':'Node not installed'})
    if not a.skip_benchmark:
        steps.append(run_step('backend_benchmark',[sys.executable,str(SCRIPTS/'benchmark_core.py'),'--samples','100','--json-out',str(out/'core-benchmark.json')],ROOT,out,a.timeout,env))
    if a.with_cargo:
        cargo=shutil.which('cargo')
        if cargo:steps.append(run_step('cargo_check',[cargo,'check'],ROOT/'src-tauri',out,max(a.timeout,300),env))
        else:steps.append({'name':'cargo_check','status':'SKIP','reason':'cargo absent'})
    if a.pid:
        trace=out/'process-telemetry.jsonl'
        steps.append(run_step('process_capture',[sys.executable,str(SCRIPTS/'diagnostics/process_sampler.py'),'--pid',str(a.pid),'--seconds',str(a.sample_seconds),'--out',str(trace)],ROOT,out,a.sample_seconds+20,env))
        if trace.exists():steps.append(run_step('process_analysis',[sys.executable,str(SCRIPTS/'diagnostics/analyze_telemetry.py'),str(trace),'--out',str(out/'process-analysis.json')],ROOT,out,a.timeout,env))
    overall='FAIL' if any(x['status'] in ('FAIL','ERROR','TIMEOUT') for x in steps) else 'PASS_WITH_SKIPS' if any(x['status']=='SKIP' for x in steps) else 'PASS_PORTABLE_ONLY'
    summary={'schema':1,'overall':overall,'steps':steps,'hardware_qualification':'NOT_RUN',
             'hardware_notes':'Run Windows native measurements and actual STT/NPU/GPU tests independently; portable PASS cannot certify them.'}
    (out/'diagnostic-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    if a.make_bundle:
        bundle(out,out/'diagnostics-bundle.zip')
    print(json.dumps({'overall':overall,'steps':[(x['name'],x['status']) for x in steps],'output':str(out)},indent=2))
    return 2 if overall=='FAIL' else 0

if __name__=='__main__':raise SystemExit(main())
