from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROVISIONAL_GATES = {
    "core_steady_private_ws_mib_max": 2560,
    "strict_logical_managed_mib_max": 2816,
    "startup_commit_delta_mib_max": 3072,
    "idle_shell_private_ws_mib_max": 500,
    "dashboard_delta_private_ws_mib_max": 350,
    "idle_cpu_median_pct_max": 0.5,
    "idle_cpu_p95_pct_max": 1.5,
    "orb_balanced_gpu_median_pct_max": 3.0,
    "orb_balanced_gpu_p95_pct_max": 6.0,
    "bridge_p95_ms_max": 15.0,
    "control_event_p95_ms_max": 35.0,
    "stt_partial_p95_ms_max": 200.0,
    "stt_final_npu_p95_ms_max": 700.0,
    "stt_final_gpu_p95_ms_max": 1000.0,
    "stt_final_cpu_p95_ms_max": 1800.0,
    "accelerator_compile_timeout_s": 45.0,
    "cpu_compile_timeout_s": 60.0,
    "warm_accelerator_load_s_max": 10.0,
    "barge_in_silence_p95_ms_max": 120.0,
    "barge_in_capture_ready_p95_ms_max": 200.0,
    "owned_worker_cleanup_s_max": 2.0,
    "cold_shell_start_p95_s_max": 3.0,
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit(root: Path) -> str | None:
    try:
        cp = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=3)
        return cp.stdout.strip() if cp.returncode == 0 else None
    except Exception:
        return None


@dataclass(slots=True)
class BenchmarkRecord:
    scenario: str
    started_at: float = field(default_factory=time.time)
    commit: str | None = None
    os: str = field(default_factory=lambda: platform.platform())
    python: str = field(default_factory=platform.python_version)
    machine: str = field(default_factory=platform.machine)
    gates: dict[str, Any] = field(default_factory=lambda: dict(PROVISIONAL_GATES))
    metadata: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return out
