#!/usr/bin/env python3
import argparse,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def pct(v,q):
 v=sorted(float(x) for x in v if x is not None and math.isfinite(float(x)))
 if not v:return None
 x=(len(v)-1)*q;lo=math.floor(x);hi=math.ceil(x);return v[lo] if lo==hi else v[lo]+(v[hi]-v[lo])*(x-lo)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('metrics');ap.add_argument('--scenario',choices=['idle_shell','certified_core','orb_balanced','orb_eco'],default='idle_shell');ap.add_argument('--desktop-summary',default='');ap.add_argument('--thresholds',default=str(ROOT/'qualification_thresholds.json'));ap.add_argument('--json-out',default='');a=ap.parse_args();d=load(a.metrics);s=d.get('samples') or [];g=load(a.thresholds)['gates'];pws=[float(x['private_working_set_mib']) for x in s if x.get('private_working_set_mib') is not None];ws=[float(x['working_set_mib']) for x in s if x.get('working_set_mib') is not None];pb=[float(x['private_bytes_mib']) for x in s if x.get('private_bytes_mib') is not None];gpu=[float(x['gpu_3d_percent']) for x in s if x.get('gpu_3d_percent') is not None];cpu=[]
 for x,y in zip(s,s[1:]):
  dt=max(.001,(float(y.get('ts',0))-float(x.get('ts',0)))/1000);cpu.append(max(0,float(y.get('process_cpu_seconds',0))-float(x.get('process_cpu_seconds',0)))/dt/max(1,float(y.get('logical_processors') or 1))*100)
 m={'private_working_set_mib':{'median':pct(pws,.5),'p95':pct(pws,.95),'peak':max(pws) if pws else None},'working_set_mib':{'median':pct(ws,.5),'p95':pct(ws,.95)},'private_bytes_mib':{'median':pct(pb,.5),'p95':pct(pb,.95)},'process_cpu_percent':{'median':pct(cpu,.5),'p95':pct(cpu,.95)},'gpu_3d_percent':{'median':pct(gpu,.5),'p95':pct(gpu,.95)}};gates=[]
 def gate(n,v,l,u,required=True):gates.append({'name':n,'status':('FAIL' if required else 'WARN') if v is None else ('PASS' if v<=l else 'FAIL'),'value':v,'limit':l,'unit':u})
 if not s:gate('metrics samples present',None,0,'samples')
 if a.scenario=='idle_shell':gate('idle private working set p95',m['private_working_set_mib']['p95'],g['idle_shell_private_working_set_mib'],'MiB');gate('idle CPU median',m['process_cpu_percent']['median'],g['idle_cpu_median_percent'],'%');gate('idle CPU p95',m['process_cpu_percent']['p95'],g['idle_cpu_p95_percent'],'%')
 elif a.scenario=='certified_core':
  gate('certified-core private working set p95',m['private_working_set_mib']['p95'],g['certified_core_private_working_set_mib'],'MiB')
  summary=load(a.desktop_summary) if a.desktop_summary else {}
  before=summary.get('committed_mib_before');after=summary.get('committed_mib_after')
  delta=max(0,float(after)-float(before)) if before is not None and after is not None else None
  gate('certified-core system commit delta',delta,g['certified_core_system_commit_delta_mib'],'MiB')
 elif a.scenario=='orb_balanced':gate('orb balanced GPU median',m['gpu_3d_percent']['median'],g['orb_balanced_gpu_median_percent'],'%',False);gate('orb balanced GPU p95',m['gpu_3d_percent']['p95'],g['orb_balanced_gpu_p95_percent'],'%',False)
 else:gate('orb eco GPU median',m['gpu_3d_percent']['median'],g['orb_eco_gpu_median_percent'],'%',False)
 out={'schema':1,'scenario':a.scenario,'sample_count':len(s),'metrics':m,'gates':gates,'overall':'FAIL' if any(x['status']=='FAIL' for x in gates) else ('WARN' if any(x['status']=='WARN' for x in gates) else 'PASS')};print(json.dumps(out,indent=2));
 if a.json_out:Path(a.json_out).write_text(json.dumps(out,indent=2)+'\n')
 return 2 if out['overall']=='FAIL' else 0
if __name__=='__main__':raise SystemExit(main())
