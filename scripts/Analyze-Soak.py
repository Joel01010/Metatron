#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,statistics
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('metrics');ap.add_argument('--json-out',default='');ap.add_argument('--max-growth-mib-per-hour',type=float,default=64.0);a=ap.parse_args()
 d=json.loads(Path(a.metrics).read_text(encoding='utf-8-sig'));s=[x for x in d.get('samples',[]) if x.get('private_working_set_mib') is not None]
 if len(s)<5: out={'schema':1,'version':'1.4.0','status':'FAIL','reason':'insufficient complete samples'};rc=2
 else:
  xs=[(x['ts']-s[0]['ts'])/3600000 for x in s];ys=[float(x['private_working_set_mib']) for x in s];xm=sum(xs)/len(xs);ym=sum(ys)/len(ys);den=sum((x-xm)**2 for x in xs);slope=sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den if den else 0.0
  q=max(1,len(ys)//4);delta=statistics.median(ys[-q:])-statistics.median(ys[:q]);out={'schema':1,'version':'1.4.0','status':'PASS' if slope<=a.max_growth_mib_per_hour else 'FAIL','samples':len(s),'duration_hours':round(xs[-1],4),'private_ws_min_mib':min(ys),'private_ws_peak_mib':max(ys),'private_ws_median_mib':statistics.median(ys),'slope_mib_per_hour':round(slope,3),'first_last_quartile_delta_mib':round(delta,3),'gate_mib_per_hour':a.max_growth_mib_per_hour};rc=0 if out['status']=='PASS' else 2
 print(json.dumps(out,indent=2));
 if a.json_out:Path(a.json_out).write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
 return rc
if __name__=='__main__':raise SystemExit(main())
