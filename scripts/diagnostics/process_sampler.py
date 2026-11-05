#!/usr/bin/env python3
"""Bounded, privacy-minimal process-tree telemetry; psutil required.
No process command lines, usernames, environment, sockets, transcript or audio collected.
Windows GPU and system commit measurements are deliberately NOT fabricated here.
"""
import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import psutil
except ImportError:
    raise SystemExit('psutil not installed: install into the project test virtual environment only')

MIB = 1024 * 1024


def identity(pid):
    try:
        p = psutil.Process(pid)
        return p, p.create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None, None


def read_tree(root, started):
    """Never follow a reused root PID; tolerate inaccessible transient children."""
    try:
        if abs(root.create_time() - started) > .001:
            return [], 'root_pid_reused'
        if not root.is_running() or root.status() == psutil.STATUS_ZOMBIE:
            return [], 'root_exited'
        procs = [root] + root.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return [], 'root_exited'
    except psutil.AccessDenied:
        return [], 'root_access_denied'
    return procs, None


def snapshot(root, started):
    procs, error = read_tree(root, started)
    totals = dict(rss_mib=0., private_mib=0., cpu_seconds=0., read_mib=0., write_mib=0.,
                  threads=0, handles=0)
    counts = dict(memory=0, private=0, cpu=0, io=0, threads=0, handles=0)
    recorded = []
    for p in procs:
        try:
            with p.oneshot():
                info = p.memory_info()
                totals['rss_mib'] += info.rss / MIB
                counts['memory'] += 1
                try:
                    full = p.memory_full_info()
                    private = getattr(full, 'uss', None)
                    if private is not None:
                        totals['private_mib'] += private / MIB
                        counts['private'] += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess, NotImplementedError):
                    pass
                try:
                    cpu = p.cpu_times()
                    totals['cpu_seconds'] += cpu.user + cpu.system
                    counts['cpu'] += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                try:
                    io = p.io_counters()
                    totals['read_mib'] += io.read_bytes / MIB
                    totals['write_mib'] += io.write_bytes / MIB
                    counts['io'] += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError, NotImplementedError):
                    pass
                try:
                    totals['threads'] += p.num_threads()
                    counts['threads'] += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                try:
                    totals['handles'] += p.num_handles()
                    counts['handles'] += 1
                except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                    pass
                recorded.append(p.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    vm = psutil.virtual_memory()
    return dict(ts=int(time.time() * 1000), process_count=len(recorded),
                process_ids=recorded, root_error=error,
                rss_mib=round(totals['rss_mib'], 3) if counts['memory'] == len(recorded) and recorded else None,
                private_mib=round(totals['private_mib'], 3) if counts['private'] == len(recorded) and recorded else None,
                cpu_seconds=round(totals['cpu_seconds'], 4) if counts['cpu'] == len(recorded) and recorded else None,
                read_mib=round(totals['read_mib'], 3) if counts['io'] == len(recorded) and recorded else None,
                write_mib=round(totals['write_mib'], 3) if counts['io'] == len(recorded) and recorded else None,
                thread_count=totals['threads'] if counts['threads'] == len(recorded) and recorded else None,
                handle_count=totals['handles'] if counts['handles'] == len(recorded) and recorded and platform.system() == 'Windows' else None,
                sample_coverage=counts, system_available_mib=round(vm.available/MIB, 3),
                system_used_percent=vm.percent, system_commit_mib=None,
                gpu_shared_mib=None, gpu_dedicated_mib=None, gpu_3d_percent=None)


def run(pid, seconds, interval, out):
    root, started = identity(pid)
    if root is None:
        raise ValueError(f'root PID {pid} does not exist or is inaccessible')
    out.parent.mkdir(parents=True, exist_ok=True)
    header = dict(schema=1, kind='metatron_process_telemetry', platform=platform.system(),
                  started_at=datetime.now(timezone.utc).isoformat(), pid=pid,
                  root_create_time=started, interval_s=interval,
                  measurement_notes={'private_mib':'USS: unique resident memory, not Windows private working set',
                                     'rss_mib':'Sum of process RSS; shared pages may be double counted',
                                     'system_commit_mib':'unavailable: use Collect-WindowsMetrics.ps1',
                                     'gpu':'unavailable: use Collect-WindowsMetrics.ps1'},
                  privacy='No names, paths, arguments, user IDs or environment are captured')
    end = time.monotonic() + seconds
    n = 0
    with out.open('w', encoding='utf-8') as f:
        f.write(json.dumps({'meta': header}) + '\n')
        while True:
            target = time.monotonic()
            row = snapshot(root, started)
            f.write(json.dumps({'sample': row}, allow_nan=False) + '\n')
            f.flush()
            n += 1
            if row['root_error']:
                break
            delay = min(interval - (time.monotonic() - target), end - time.monotonic())
            if delay <= 0:
                break
            time.sleep(delay)
    print(f'Saved {n} samples to {out}')
    return 0 if n >= 2 else 2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', type=int, required=True)
    ap.add_argument('--seconds', type=int, default=60)
    ap.add_argument('--interval', type=float, default=1.)
    ap.add_argument('--out', type=Path, required=True)
    a=ap.parse_args()
    if a.pid <= 0 or not 2 <= a.seconds <= 86400 or not .2 <= a.interval <= 60:
        ap.error('pid > 0; seconds 2..86400; interval 0.2..60 required')
    try:
        return run(a.pid, a.seconds, a.interval, a.out)
    except (ValueError, PermissionError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2

if __name__=='__main__':
    raise SystemExit(main())
