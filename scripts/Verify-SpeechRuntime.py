#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from metatron.config import AppConfig
from metatron.core import Metatron
from metatron.speech import _split_command
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--command-json',default='');ap.add_argument('--json-out',default='');a=ap.parse_args();cmd=json.loads(a.command_json) if a.command_json else _split_command(os.environ.get('METATRON_SPEECH_CMD',''))
 if not cmd:
  out={'schema':1,'configured':False,'verified':False,'reason':'METATRON_SPEECH_CMD is not configured'};print(json.dumps(out,indent=2));Path(a.json_out).write_text(json.dumps(out,indent=2)+'\n') if a.json_out else None;return 3
 with tempfile.TemporaryDirectory(prefix='metatron-speech-probe-') as td:
  app=Metatron(AppConfig(data_dir=Path(td),enable_background_maintenance=False,tts_enabled=False));app.speech.command=list(cmd);start=time.perf_counter()
  try:
   st=app.speech.start();ready=(time.perf_counter()-start)*1000;ps=time.perf_counter();ping=app.speech.request('ping',{},timeout_s=10);pingms=(time.perf_counter()-ps)*1000;dev=app.speech.request('list_ov_devices',{},timeout_s=10);actual=st.get('actual_device') or {};out={'schema':1,'configured':True,'verified':bool(actual.get('kind')),'ready_ms':round(ready,2),'ping_ms':round(pingms,2),'ping':ping,'runtime_devices':dev,'status':st,'actual_device':actual};rc=0 if out['verified'] else 2
  except Exception as e:out={'schema':1,'configured':True,'verified':False,'error':f'{type(e).__name__}: {e}','status':app.speech.status()};rc=2
  finally:app.close()
 print(json.dumps(out,indent=2,default=str));Path(a.json_out).write_text(json.dumps(out,indent=2,default=str)+'\n') if a.json_out else None;return rc
if __name__=='__main__':raise SystemExit(main())
