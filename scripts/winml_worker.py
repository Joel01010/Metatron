from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path


def _initialize():
    # Microsoft currently documents this workaround for the Python framework-
    # dependent Windows ML package because winrt-runtime may ship msvcp140.dll.
    try:
        from importlib import metadata
        site = Path(str(metadata.distribution('winrt-runtime').locate_file('')))
        dll = site / 'winrt' / 'msvcp140.dll'
        if dll.exists():
            dll.unlink()
    except Exception:
        pass
    from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import InitializeOptions, initialize
    import winui3.microsoft.windows.ai.machinelearning as winml
    import onnxruntime as ort
    handle = initialize(options=InitializeOptions.ON_NO_MATCH_SHOW_UI)
    handle.__enter__()
    return handle, winml, ort


def _version(pkg):
    if pkg is None: return None
    try:
        v=pkg.version
        return f"{v.major}.{v.minor}.{v.build}.{v.revision}"
    except Exception:
        return None


def _devices(ort):
    out=[]
    fn=getattr(ort,'get_ep_devices',None)
    if not callable(fn): return out
    for i,d in enumerate(fn()):
        hw=getattr(d,'hardware_device',None)
        t=getattr(getattr(hw,'type',None),'name',str(getattr(hw,'type','')))
        out.append({
            'index':i,'ep_name':str(getattr(d,'ep_name','')),
            'kind':str(t).upper(),'name':str(getattr(hw,'name','') or ''),
            'vendor':str(getattr(hw,'vendor','') or ''),'device_id':str(getattr(hw,'device_id','') or ''),
        })
    return out


def catalog(winml, ort):
    cat=winml.ExecutionProviderCatalog.get_default()
    providers=[]
    for p in cat.find_all_providers():
        providers.append({
            'name':str(p.name),'ready_state':str(getattr(getattr(p,'ready_state',None),'name',getattr(p,'ready_state',''))),
            'version':_version(getattr(p,'package_id',None)),
            'library_path':str(getattr(p,'library_path','') or ''),
        })
    return {'providers':providers,'devices':_devices(ort)}


def ensure(winml, ort, names=None):
    # With no explicit list, prepare every provider the Windows ML catalog says
    # is available. This is future-proof: a new certified NPU EP can be used by
    # Metatron without a source-code update.
    wanted=set(names) if names else None
    cat=winml.ExecutionProviderCatalog.get_default()
    results=[]
    for p in cat.find_all_providers():
        if wanted is not None and str(p.name) not in wanted: continue
        before=str(getattr(getattr(p,'ready_state',None),'name',getattr(p,'ready_state','')))
        ok=False; err=''
        try:
            result=p.ensure_ready_async().get()
            status=str(getattr(getattr(result,'status',None),'name',getattr(result,'status','')))
            if getattr(p,'library_path',''):
                try: ort.register_execution_provider_library(str(p.name), str(p.library_path))
                except Exception: pass
            ok='SUCCESS' in status.upper() or 'READY' in str(getattr(getattr(p,'ready_state',None),'name','')).upper()
        except Exception as e:
            err=f'{type(e).__name__}: {e}'
        results.append({'name':str(p.name),'before':before,'ready':ok,'error':err,'library_path':str(getattr(p,'library_path','') or '')})
    return {'results':results,'devices':_devices(ort)}


def handle(req, winml, ort):
    cmd=str(req.get('cmd') or '')
    p=req.get('params') or {}
    if cmd=='catalog': return catalog(winml,ort)
    if cmd=='ensure': return ensure(winml,ort,p.get('names'))
    if cmd=='devices': return {'devices':_devices(ort)}
    raise ValueError(f'unknown cmd {cmd!r}')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--once',choices=['catalog','ensure','devices']);ap.add_argument('--names',default='')
    a=ap.parse_args()
    handle_ctx,winml,ort=_initialize()
    try:
        if a.once:
            params={'names':[x for x in a.names.split(',') if x]} if a.names else {}
            print(json.dumps(handle({'cmd':a.once,'params':params},winml,ort),separators=(',',':')))
            return
        for line in sys.stdin:
            line=line.strip()
            if not line: continue
            rid=None
            try:
                req=json.loads(line);rid=req.get('id');result=handle(req,winml,ort);out={'id':rid,'ok':True,'result':result}
            except Exception as e:
                out={'id':rid,'ok':False,'error':{'message':str(e),'type':type(e).__name__}}
            print(json.dumps(out,separators=(',',':')),flush=True)
    finally:
        handle_ctx.__exit__(None,None,None)

if __name__=='__main__':
    try: main()
    except Exception as e:
        print(json.dumps({'ok':False,'error':{'message':str(e),'trace':traceback.format_exc(limit=3)}}))
        raise
