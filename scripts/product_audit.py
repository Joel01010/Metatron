#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from metatron import __version__
class P(HTMLParser):
 def __init__(self):super().__init__();self.ids=[]
 def handle_starttag(self,t,a):self.ids += [v for k,v in a if k=='id' and v]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--json-out',default='');a=ap.parse_args();checks=[]
 def add(n,ok,d=''):checks.append({'name':n,'ok':bool(ok),'detail':d})
 html=(ROOT/'ui/index.html').read_text(encoding='utf-8');js=(ROOT/'ui/app.js').read_text(encoding='utf-8');srv=(ROOT/'metatron/server.py').read_text(encoding='utf-8');rust=(ROOT/'src-tauri/src/main.rs').read_text(encoding='utf-8');cfg=json.loads((ROOT/'src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
 p=P();p.feed(html);dupes=sorted({x for x in p.ids if p.ids.count(x)>1});add('unique_html_ids',not dupes,f'{len(p.ids)} ids' if not dupes else str(dupes))
 views={'command','dictation','history','vocabulary','hardware','models','voice','metrics','tasks','agents','diagnostics','settings'};missing=[v for v in views if f'id="view-{v}"' not in html];add('professional_views_present',not missing,f'{len(views)} views' if not missing else str(missing))
 known=set(re.findall(r'if cmd == ["\']([^"\']+)',srv));inv=set(re.findall(r"invoke\(['\"]([^'\"]+)",js));inv.update(re.findall(r"agentAction\(['\"]([^'\"]+)",js));unknown=sorted(inv-known-{'bridge.live_events','backend_command','window_command'});add('ui_backend_commands_exist',not unknown,str(unknown) if unknown else f'{len(inv)} commands checked')
 body=re.search(r'fn main_allowed\(cmd: &str\).*?matches!\(cmd,(.*?)\n\s*\)\n}',rust,re.S);allowed=set(re.findall(r'"([A-Za-z0-9_.-]+)"',body.group(1) if body else ''));unauth=sorted((inv-{'backend_command','window_command'})-allowed);add('dashboard_command_allowlist',not unauth and bool(allowed),str(unauth) if unauth else f'{len(allowed)} commands authorized')
 csp=cfg.get('app',{}).get('security',{}).get('csp') or '';add('csp_enabled',bool(csp) and 'unsafe-eval' not in csp.lower(),csp);add('version_consistent',str(cfg.get('version'))==__version__,f'python={__version__}, tauri={cfg.get("version")}')
 orbs=[f for f in ROOT.rglob('orb-renderer.js') if not any(part in {'build','target','.venv','node_modules'} for part in f.relative_to(ROOT).parts[:-1])];add('single_orb_renderer',len(orbs)==1,','.join(str(x.relative_to(ROOT)) for x in orbs))
 hard=[]
 for f in ROOT.rglob('*'):
  if not f.is_file() or any(part in {'.git','build','target','.venv','node_modules','__pycache__','scripts'} for part in f.relative_to(ROOT).parts[:-1]) or f.parent == ROOT/'scripts' or f.suffix.lower() in {'.pyc','.zip','.png','.jpg','.ico'}:continue
  try:text=f.read_text(errors='ignore')
  except:continue
  if re.search(r'(?i)z:\\\\?metatron',text):hard.append(str(f.relative_to(ROOT)))
 add('no_machine_specific_z_drive',not hard,str(hard) if hard else 'clean')
 req=['Build-Windows.ps1','Invoke-MetatronFullValidation.ps1','Invoke-MetatronV14Qualification.ps1','Collect-WindowsMetrics.ps1','Collect-SupportBundle.ps1','Verify-Accelerators.py','Verify-OpenVINODevices.py','Verify-SpeechRuntime.py','Test-WindowsAudio.py','Test-WindowsTTSInterrupt.py','Test-OrbWindow.ps1','Measure-MetatronSoak.ps1','Analyze-Soak.py','Verify-WindowsArtifacts.ps1','Test-PowerShellScripts.ps1','Test-WindowsPrerequisites.ps1','Bootstrap-Windows.ps1'];missing=[x for x in req if not (ROOT/'scripts'/x).is_file()];add('full_system_tooling_present',not missing,str(missing) if missing else 'all present')
 out={'schema':1,'version':__version__,'passed':sum(c['ok'] for c in checks),'total':len(checks),'checks':checks};print(json.dumps(out,indent=2));
 if a.json_out:Path(a.json_out).write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
 return 0 if out['passed']==out['total'] else 2
if __name__=='__main__':raise SystemExit(main())
