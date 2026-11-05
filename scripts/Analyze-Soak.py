#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def finite(values):
    out=[]
    for value in values:
        if value is None:
            continue
        try:
            value=float(value)
        except (TypeError,ValueError):
            continue
        if math.isfinite(value):
            out.append(value)
    return out


def slope_per_hour(samples, field):
    rows=[]
    for sample in samples:
        value=sample.get(field)
        ts=sample.get('ts')
        if value is None or ts is None:
            continue
        try:
            rows.append((float(ts),float(value)))
        except (TypeError,ValueError):
            continue
    if len(rows)<2:
        return None
    t0=rows[0][0]
    xs=[(ts-t0)/3600000.0 for ts,_ in rows]
    ys=[value for _,value in rows]
    xm=sum(xs)/len(xs)
    ym=sum(ys)/len(ys)
    den=sum((x-xm)**2 for x in xs)
    if den<=0:
        return 0.0
    return sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den


def quartile_delta(values):
    values=finite(values)
    if not values:
        return None
    q=max(1,len(values)//4)
    return statistics.median(values[-q:])-statistics.median(values[:q])


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('metrics')
    ap.add_argument('--json-out',default='')
    ap.add_argument('--max-growth-mib-per-hour',type=float,default=64.0)
    ap.add_argument('--max-quartile-delta-mib',type=float,default=128.0)
    ap.add_argument('--max-private-ws-mib',type=float,default=2560.0)
    ap.add_argument('--max-private-bytes-mib',type=float,default=3072.0)
    ap.add_argument('--max-private-bytes-growth-mib-per-hour',type=float,default=64.0)
    ap.add_argument('--max-private-bytes-quartile-delta-mib',type=float,default=128.0)
    ap.add_argument('--min-complete-ratio',type=float,default=0.95)
    ap.add_argument('--max-handle-growth',type=float,default=200.0)
    ap.add_argument('--max-thread-growth',type=float,default=30.0)
    args=ap.parse_args()

    data=json.loads(Path(args.metrics).read_text(encoding='utf-8-sig'))
    all_samples=data.get('samples') or []
    complete=[x for x in all_samples if x.get('private_working_set_mib') is not None]
    private_complete=[x for x in all_samples if x.get('private_bytes_mib') is not None]
    complete_ratio=len(complete)/len(all_samples) if all_samples else 0.0
    private_complete_ratio=len(private_complete)/len(all_samples) if all_samples else 0.0

    failures=[]
    warnings=[]
    if len(complete)<5:
        failures.append('insufficient complete samples')

    expected_seconds=float(data.get('duration_seconds') or 0)
    observed_seconds=0.0
    if len(all_samples)>=2:
        observed_seconds=max(0.0,(float(all_samples[-1].get('ts',0))-float(all_samples[0].get('ts',0)))/1000.0)
    if expected_seconds>0 and observed_seconds < expected_seconds*0.90:
        failures.append('capture ended before 90% of requested duration')
    required_ratio=max(0.0,min(1.0,args.min_complete_ratio))
    if complete_ratio < required_ratio:
        failures.append('too many incomplete private-working-set samples')
    if private_complete_ratio < required_ratio:
        failures.append('too many incomplete private-bytes samples')

    pws=finite(x.get('private_working_set_mib') for x in complete)
    slope=slope_per_hour(complete,'private_working_set_mib')
    delta=quartile_delta(pws)
    peak=max(pws) if pws else None
    median=statistics.median(pws) if pws else None
    minimum=min(pws) if pws else None

    if slope is None:
        failures.append('memory growth slope unavailable')
    elif slope>args.max_growth_mib_per_hour:
        failures.append(f'private working-set growth {slope:.2f} MiB/h exceeds gate')
    if delta is None:
        failures.append('quartile drift unavailable')
    elif delta>args.max_quartile_delta_mib:
        failures.append(f'first/last quartile drift {delta:.2f} MiB exceeds gate')
    if peak is None:
        failures.append('private working-set peak unavailable')
    elif peak>args.max_private_ws_mib:
        failures.append(f'private working-set peak {peak:.2f} MiB exceeds gate')

    private_bytes=finite(x.get('private_bytes_mib') for x in private_complete)
    private_bytes_slope=slope_per_hour(private_complete,'private_bytes_mib')
    private_bytes_delta=quartile_delta(private_bytes)
    private_bytes_peak=max(private_bytes) if private_bytes else None
    private_bytes_median=statistics.median(private_bytes) if private_bytes else None
    if private_bytes_slope is None:
        failures.append('private-bytes growth slope unavailable')
    elif private_bytes_slope>args.max_private_bytes_growth_mib_per_hour:
        failures.append(f'private-bytes growth {private_bytes_slope:.2f} MiB/h exceeds gate')
    if private_bytes_delta is None:
        failures.append('private-bytes quartile drift unavailable')
    elif private_bytes_delta>args.max_private_bytes_quartile_delta_mib:
        failures.append(f'private-bytes first/last quartile drift {private_bytes_delta:.2f} MiB exceeds gate')
    if private_bytes_peak is None:
        failures.append('private-bytes peak unavailable')
    elif private_bytes_peak>args.max_private_bytes_mib:
        failures.append(f'private-bytes peak {private_bytes_peak:.2f} MiB exceeds gate')

    system_commit=finite(x.get('system_committed_mib') for x in all_samples)
    system_commit_pct=finite(x.get('system_commit_percent') for x in all_samples)

    handle_delta=quartile_delta(x.get('handle_count') for x in all_samples)
    thread_delta=quartile_delta(x.get('thread_count') for x in all_samples)
    handle_slope=slope_per_hour(all_samples,'handle_count')
    thread_slope=slope_per_hour(all_samples,'thread_count')
    if handle_delta is not None and handle_delta>args.max_handle_growth:
        warnings.append(f'handle count grew by {handle_delta:.0f} across quartiles')
    if thread_delta is not None and thread_delta>args.max_thread_growth:
        warnings.append(f'thread count grew by {thread_delta:.0f} across quartiles')

    churn=sum(len(x.get('process_added_pids') or [])+len(x.get('process_removed_pids') or []) for x in all_samples)
    max_sample_ms=max(finite(x.get('sample_elapsed_ms') for x in all_samples),default=None)
    max_overrun_ms=max(finite(x.get('interval_overrun_ms') for x in all_samples),default=None)

    status='FAIL' if failures else ('WARN' if warnings else 'PASS')
    out={
        'schema':2,
        'version':'1.4.0',
        'status':status,
        'samples_total':len(all_samples),
        'samples_complete':len(complete),
        'complete_ratio':round(complete_ratio,4),
        'private_bytes_complete_ratio':round(private_complete_ratio,4),
        'requested_duration_seconds':expected_seconds,
        'observed_duration_seconds':round(observed_seconds,2),
        'private_ws_min_mib':minimum,
        'private_ws_peak_mib':peak,
        'private_ws_median_mib':median,
        'slope_mib_per_hour':None if slope is None else round(slope,3),
        'first_last_quartile_delta_mib':None if delta is None else round(delta,3),
        'private_bytes_peak_mib':private_bytes_peak,
        'private_bytes_median_mib':private_bytes_median,
        'private_bytes_slope_mib_per_hour':None if private_bytes_slope is None else round(private_bytes_slope,3),
        'private_bytes_first_last_quartile_delta_mib':None if private_bytes_delta is None else round(private_bytes_delta,3),
        'system_commit_first_mib':system_commit[0] if system_commit else None,
        'system_commit_last_mib':system_commit[-1] if system_commit else None,
        'system_commit_peak_pct':max(system_commit_pct) if system_commit_pct else None,
        'gates':{
            'max_growth_mib_per_hour':args.max_growth_mib_per_hour,
            'max_quartile_delta_mib':args.max_quartile_delta_mib,
            'max_private_ws_mib':args.max_private_ws_mib,
            'max_private_bytes_mib':args.max_private_bytes_mib,
            'max_private_bytes_growth_mib_per_hour':args.max_private_bytes_growth_mib_per_hour,
            'max_private_bytes_quartile_delta_mib':args.max_private_bytes_quartile_delta_mib,
            'min_complete_ratio':args.min_complete_ratio,
        },
        'handle_count_quartile_delta':None if handle_delta is None else round(handle_delta,3),
        'handle_count_slope_per_hour':None if handle_slope is None else round(handle_slope,3),
        'thread_count_quartile_delta':None if thread_delta is None else round(thread_delta,3),
        'thread_count_slope_per_hour':None if thread_slope is None else round(thread_slope,3),
        'process_churn_events':churn,
        'max_sample_elapsed_ms':max_sample_ms,
        'max_interval_overrun_ms':max_overrun_ms,
        'failures':failures,
        'warnings':warnings,
    }
    print(json.dumps(out,indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    return 2 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
