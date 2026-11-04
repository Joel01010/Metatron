from __future__ import annotations
import os, platform, shutil, time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from . import __version__
from .db import CURRENT_SCHEMA_VERSION
@dataclass(slots=True)
class DiagnosticsService:
    app:Any
    def runtime_inventory(self):
        cfg=self.app.config; speech=self.app.speech.status(); tts=self.app.tts.status(); providers={str(p.get('id')):bool(p.get('available')) for p in (tts.get('providers') or []) if isinstance(p,dict)}
        exists=lambda v: bool(v) and Path(v).expanduser().exists()
        return [
          {"id":"speech","label":"Speech / STT","role":"dictation","configured":bool(speech.get('configured')),"ready":bool(speech.get('configured')),"detail":"JSONL speech sidecar configured" if speech.get('configured') else "Speech sidecar command is not configured","setup_script":"Setup-SpeechRuntime.ps1"},
          {"id":"windows-ml","label":"Windows ML","role":"accelerators","configured":bool(cfg.winml_python),"ready":exists(cfg.winml_python),"detail":cfg.winml_python or "Dedicated Windows ML environment not configured","setup_script":"Setup-WindowsML.ps1"},
          {"id":"kokoro","label":"Kokoro","role":"premium TTS","configured":bool(cfg.kokoro_python and cfg.kokoro_model_path and cfg.kokoro_voices_path),"ready":bool(providers.get('kokoro')),"detail":cfg.kokoro_model_path or "Premium local voice model not configured","setup_script":"Setup-Kokoro-TTS.ps1"},
          {"id":"piper","label":"Piper","role":"light TTS","configured":bool(cfg.piper_bin and cfg.piper_model_path),"ready":bool(providers.get('piper')),"detail":cfg.piper_model_path or "Optional lightweight voice not configured","setup_script":""},
          {"id":"s1-mini","label":"S1-mini","role":"semantic cleanup","configured":bool(cfg.s1_command),"ready":bool(cfg.s1_command),"detail":"Disposable cleanup worker configured" if cfg.s1_command else "Optional semantic cleanup worker not configured","setup_script":"Setup-S1Mini.ps1"},
        ]
    def summary(self):
        checks=[]
        def add(k,ok,label,detail='',severity='error'): checks.append({"key":k,"ok":bool(ok),"label":label,"detail":str(detail),"severity":"ok" if ok else severity})
        d=Path(self.app.config.data_dir)
        try:
            p=d/'.metatron-write-test'; p.write_text('ok',encoding='utf-8'); p.unlink(missing_ok=True); writable=True; detail=str(d)
        except Exception as e: writable=False; detail=str(e)
        add('data_dir',writable,'Data directory writable',detail)
        add('database_schema',self.app.db.schema_version==CURRENT_SCHEMA_VERSION,'Database schema current',f"v{self.app.db.schema_version} / v{CURRENT_SCHEMA_VERSION}")
        hw=self.app.hardware.status(); n=int((hw.get('counts') or {}).get('npu') or 0); g=int((hw.get('counts') or {}).get('gpu') or 0); add('accelerator_route',bool(n or g),'Accelerated inference route available',f"{n} routable NPU(s), {g} routable GPU(s)",severity='warning')
        sp=self.app.speech.status(); add('speech_runtime',bool(sp.get('configured')),'Speech runtime configured','configured' if sp.get('configured') else 'Run Setup-SpeechRuntime.ps1 or configure METATRON_SPEECH_CMD',severity='warning')
        t=self.app.tts.status(); ps=t.get('providers') or []; avail=[p for p in ps if not isinstance(p,dict) or bool(p.get('available'))]; pd=', '.join((f"{p.get('id') or p.get('name') or 'provider'} ({'ready' if p.get('available') else 'unavailable'})" if isinstance(p,dict) else str(p)) for p in ps) or 'No provider detected'; add('tts_provider',bool(avail),'TTS provider available',pd,severity='warning')
        mem=self.app.memory.status(); r=float(mem.get('platform_reserved_mib') or 0); hard=float(mem.get('hard_limit_mib') or 1); add('memory_headroom',r<=hard,'Memory broker inside hard ceiling',f"{r:.0f} MiB reserved / {hard:.0f} MiB ceiling")
        add('secret_store',self.app.secrets.__class__.__name__!='MemorySecretStore' or os.name!='nt','Persistent secret store available',self.app.secrets.__class__.__name__,severity='warning')
        out={"version":__version__,"timestamp":time.time(),"platform":{"system":platform.system(),"release":platform.release(),"machine":platform.machine(),"python":platform.python_version()},"checks":checks,"counts":{"ok":sum(c['ok'] for c in checks),"warning":sum((not c['ok'] and c['severity']=='warning') for c in checks),"error":sum((not c['ok'] and c['severity']=='error') for c in checks)},"tools":{"git":shutil.which('git') or '',"cargo":shutil.which('cargo') or '',"python":shutil.which('python') or shutil.which('python3') or ''}}
        out['ready_for_core_use']=out['counts']['error']==0; return out
