#!/usr/bin/env python3
"""Summarize JSONL telemetry and Windows collector JSON with missing-data-safe rules."""
import argparse
import json
import math
import statistics
from pathlib import Path


def percentile(values, pct):
    v=sorted(float(x) for x in values if isinstance(x, (float, int)) and math.isfinite(x))
    if not v: return None
    i=(len(v)-1)*pct
    lo=math.floor(i); hi=math.ceil(i)
    return round(v[lo]+(v[hi]-v[lo])*(i-lo),3)


def load(path):
    raw=Path(path).read_text(encoding='utf-8-sig')
    if raw.lstrip().startswith('{'):
        try:
            obj=json.loads(raw)
            if isinstance(obj.get('samples'),list):
                return obj.get('samples', []),obj
        except json.JSONDecodeError:
            pass
    lines=[json.loads(line) for line in raw.splitlines() if line.strip()]
    meta=next((x['meta'] for x in lines if 'meta' in x),{})
    return [x['sample'] for x in lines if 'sample' in x],meta


def summarize(samples,meta):
    win='root_pid' in meta and 'samples' in meta
    keys={'resident_mib':'working_set_mib' if win else 'rss_mib',
          'private_working_set_mib':'private_working_set_mib' if win else None,
          'private_uss_mib':None if win else 'private_mib',
          'private_commit_mib':'private_bytes_mib' if win else None,
          'system_available_mib':'system_available_mib',
          'system_commit_mib':'system_committed_mib' if win else 'system_commit_mib',
          'gpu_shared_mib':'gpu_shared_mib','gpu_dedicated_mib':'gpu_dedicated_mib',
          'gpu_3d_percent':'gpu_3d_percent','threads':'thread_count' if not win else None,
          'handles':'handle_count' if not win else None,'process_count':'process_count'}
    metrics={}
    for label,key in keys.items():
        values=[x.get(key) for x in samples if key and x.get(key) is not None]
        metrics[label]={'available':bool(values), 'valid_samples':len(values),
                        'median':percentile(values,.5),'p95':percentile(values,.95),
                        'peak':max(values) if values else None,
                        'first':values[0] if values else None,'last':values[-1] if values else None}
    cpu=[]
    for x,y in zip(samples,samples[1:]):
        a=x.get('process_cpu_seconds',x.get('cpu_seconds'));b=y.get('process_cpu_seconds',y.get('cpu_seconds'))
        if a is None or b is None:continue
        dt=(y['ts']-x['ts'])/1000
        if dt>0:
            cpu.append(max(0,(b-a)/dt)/max(1,y.get('logical_processors') or 1)*100)
    metrics['cpu_percent']={'available':bool(cpu),'median':percentile(cpu,.5),'p95':percentile(cpu,.95),'valid_samples':len(cpu)}
    missing=[k for k,v in metrics.items() if not v['available']]
    errors=[x.get('root_error') for x in samples if x.get('root_error')]
    max_gap=max(((b['ts']-a['ts'])/1000 for a,b in zip(samples,samples[1:])),default=None)
    result={'schema':1,'sample_count':len(samples),'duration_observed_s':round((samples[-1]['ts']-samples[0]['ts'])/1000,2) if len(samples)>=2 else 0,
            'max_sample_gap_s':round(max_gap,3) if max_gap is not None else None,
            'metrics':metrics,'missing_metrics':missing,'errors':errors,'limitations':[]}
    if not win:result['limitations'].append('USS is not private commit; Windows private working-set and commit require Windows native collector.')
    if meta.get('gpu_counter_error'):result['limitations'].append('GPU counters unavailable: '+str(meta['gpu_counter_error']))
    if len(samples)<2:result['limitations'].append('Insufficient samples for trend/CPU analysis.')
    if samples and max_gap and max_gap>3*max(.2,result['duration_observed_s']/max(1,len(samples)-1)):
        result['limitations'].append('Large sampling gap: metrics may have missed a peak.')
    result['status']='INCOMPLETE' if len(samples)<2 or errors else 'CAPTURED_NOT_CERTIFIED'
    return result


def compare(a,b):
    deltas={}
    for name in sorted(set(a['metrics'])&set(b['metrics'])):
        av=a['metrics'][name].get('p95');bv=b['metrics'][name].get('p95')
        deltas[name]={'baseline_p95':av,'candidate_p95':bv,'delta':round(bv-av,3) if av is not None and bv is not None else None,
                     'percent':round((bv-av)/av*100,2) if av not in (None,0) and bv is not None else None}
    return deltas


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('telemetry',type=Path);p.add_argument('--baseline',type=Path)
    p.add_argument('--out',type=Path);a=p.parse_args()
    samples,meta=load(a.telemetry)
    result=summarize(samples,meta)
    if a.baseline:
        old,old_meta=load(a.baseline)
        result['baseline_comparison']=compare(summarize(old,old_meta),result)
    rendered=json.dumps(result,indent=2,allow_nan=False)+'\n'
    print(rendered)
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(rendered,encoding='utf-8')
    return 0 if result['status']!='INCOMPLETE' else 2

if __name__=='__main__':raise SystemExit(main())
