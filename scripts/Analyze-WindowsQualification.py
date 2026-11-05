#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def finite(values):
    out = []
    for value in values:
        if value is None:
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value):
            out.append(value)
    return out


def pct(values, q: float):
    values = sorted(finite(values))
    if not values:
        return None
    x = (len(values) - 1) * q
    lo = math.floor(x)
    hi = math.ceil(x)
    return values[lo] if lo == hi else values[lo] + (values[hi] - values[lo]) * (x - lo)


def summarize_series(values):
    values = finite(values)
    return {
        "count": len(values),
        "median": pct(values, 0.5),
        "p95": pct(values, 0.95),
        "peak": max(values) if values else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("metrics")
    ap.add_argument(
        "--scenario",
        choices=["idle_shell", "certified_core", "orb_balanced", "orb_eco"],
        default="idle_shell",
    )
    ap.add_argument("--desktop-summary", default="")
    ap.add_argument("--thresholds", default=str(ROOT / "qualification_thresholds.json"))
    ap.add_argument("--json-out", default="")
    ap.add_argument("--min-complete-memory-ratio", type=float, default=0.95)
    args = ap.parse_args()

    data = load(args.metrics)
    samples = data.get("samples") or []
    gates_cfg = load(args.thresholds)["gates"]

    pws = [x.get("private_working_set_mib") for x in samples]
    ws = [x.get("working_set_mib") for x in samples]
    private_bytes = [x.get("private_bytes_mib") for x in samples]
    gpu = [x.get("gpu_3d_percent") for x in samples]
    gpu_shared = [x.get("gpu_shared_mib") for x in samples]
    gpu_dedicated = [x.get("gpu_dedicated_mib") for x in samples]
    handles = [x.get("handle_count") for x in samples]
    threads = [x.get("thread_count") for x in samples]
    sample_elapsed = [x.get("sample_elapsed_ms") for x in samples]
    overrun = [x.get("interval_overrun_ms") for x in samples]
    system_available = [x.get("system_available_mib") for x in samples]
    system_commit = [x.get("system_committed_mib") for x in samples]
    system_commit_pct = [x.get("system_commit_percent") for x in samples]

    cpu = []
    for first, second in zip(samples, samples[1:]):
        first_cpu = first.get("process_cpu_seconds")
        second_cpu = second.get("process_cpu_seconds")
        if first_cpu is None or second_cpu is None:
            continue
        try:
            dt = (float(second.get("ts")) - float(first.get("ts"))) / 1000.0
            logical = max(1.0, float(second.get("logical_processors") or 1))
            if dt <= 0:
                continue
            delta = float(second_cpu) - float(first_cpu)
            if delta < 0:
                continue
            cpu.append(delta / dt / logical * 100.0)
        except (TypeError, ValueError):
            continue

    complete_memory = sum(1 for x in samples if x.get("private_working_set_mib") is not None)
    complete_ratio = complete_memory / len(samples) if samples else 0.0
    process_churn_events = sum(
        len(x.get("process_added_pids") or []) + len(x.get("process_removed_pids") or []) for x in samples
    )

    metrics = {
        "private_working_set_mib": summarize_series(pws),
        "working_set_mib": summarize_series(ws),
        "private_bytes_mib": summarize_series(private_bytes),
        "process_cpu_percent": summarize_series(cpu),
        "gpu_3d_percent": summarize_series(gpu),
        "gpu_shared_mib": summarize_series(gpu_shared),
        "gpu_dedicated_mib": summarize_series(gpu_dedicated),
        "handle_count": summarize_series(handles),
        "thread_count": summarize_series(threads),
        "sample_elapsed_ms": summarize_series(sample_elapsed),
        "interval_overrun_ms": summarize_series(overrun),
        "system_available_mib": summarize_series(system_available),
        "system_committed_mib": summarize_series(system_commit),
        "system_commit_percent": summarize_series(system_commit_pct),
        "complete_memory_sample_ratio": complete_ratio,
        "process_churn_events": process_churn_events,
    }

    gates = []

    def gate_max(name, value, limit, unit, required=True):
        if value is None:
            status = "FAIL" if required else "WARN"
        else:
            status = "PASS" if value <= limit else "FAIL"
        gates.append({"name": name, "status": status, "value": value, "limit": limit, "unit": unit})

    def gate_min(name, value, limit, unit, required=True):
        if value is None:
            status = "FAIL" if required else "WARN"
        else:
            status = "PASS" if value >= limit else "FAIL"
        gates.append({"name": name, "status": status, "value": value, "limit": limit, "unit": unit})

    if not samples:
        gate_min("metrics samples present", 0, 1, "samples")
    else:
        gate_min(
            "complete private working-set sample ratio",
            round(complete_ratio, 4),
            max(0.0, min(1.0, args.min_complete_memory_ratio)),
            "ratio",
        )

    if args.scenario == "idle_shell":
        gate_max(
            "idle private working set p95",
            metrics["private_working_set_mib"]["p95"],
            gates_cfg["idle_shell_private_working_set_mib"],
            "MiB",
        )
        gate_max(
            "idle CPU median",
            metrics["process_cpu_percent"]["median"],
            gates_cfg["idle_cpu_median_percent"],
            "%",
        )
        gate_max(
            "idle CPU p95",
            metrics["process_cpu_percent"]["p95"],
            gates_cfg["idle_cpu_p95_percent"],
            "%",
        )
    elif args.scenario == "certified_core":
        gate_max(
            "certified-core private working set p95",
            metrics["private_working_set_mib"]["p95"],
            gates_cfg["certified_core_private_working_set_mib"],
            "MiB",
        )
        summary = load(args.desktop_summary) if args.desktop_summary else {}
        before = summary.get("committed_mib_before")
        after = summary.get("committed_mib_after")
        delta = max(0.0, float(after) - float(before)) if before is not None and after is not None else None
        gate_max(
            "certified-core system commit delta",
            delta,
            gates_cfg["certified_core_system_commit_delta_mib"],
            "MiB",
        )
    elif args.scenario == "orb_balanced":
        gate_max(
            "orb balanced GPU median",
            metrics["gpu_3d_percent"]["median"],
            gates_cfg["orb_balanced_gpu_median_percent"],
            "%",
            False,
        )
        gate_max(
            "orb balanced GPU p95",
            metrics["gpu_3d_percent"]["p95"],
            gates_cfg["orb_balanced_gpu_p95_percent"],
            "%",
            False,
        )
    else:
        gate_max(
            "orb eco GPU median",
            metrics["gpu_3d_percent"]["median"],
            gates_cfg["orb_eco_gpu_median_percent"],
            "%",
            False,
        )

    overall = "FAIL" if any(x["status"] == "FAIL" for x in gates) else (
        "WARN" if any(x["status"] == "WARN" for x in gates) else "PASS"
    )
    out = {
        "schema": 2,
        "scenario": args.scenario,
        "sample_count": len(samples),
        "source_schema": data.get("schema"),
        "gpu_counter_error": data.get("gpu_counter_error"),
        "metrics": metrics,
        "gates": gates,
        "overall": overall,
    }
    print(json.dumps(out, indent=2))
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return 2 if overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
