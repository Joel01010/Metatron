from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from metatron.hardware import HardwareManager, WindowsMLSessionFactory


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')


def _issue_template(report_name: str) -> str:
    return f'''---\ntitle: "Accelerator compatibility report"\nlabels: [hardware-compatibility]\n---\n\nAttach `{report_name}` and fill in:\n\n- Laptop/desktop model:\n- Windows version:\n- NPU/GPU driver versions:\n- Result expected:\n- Result observed:\n- Did Device Manager show the NPU? yes/no\n- Was the NPU reported routable? yes/no\n- Verified actual placement: NPU/GPU/CPU/unverified\n'''


def main() -> int:
    ap = argparse.ArgumentParser(description='Inspect Metatron accelerator routing and optionally prove placement.')
    ap.add_argument('--model', help='Optional ONNX model for warm-up placement proof.')
    ap.add_argument('--workload', default='verification')
    ap.add_argument('--report', default='', help='Write a privacy-conscious JSON hardware report.')
    ap.add_argument('--issue-template', default='', help='Write a GitHub issue template beside the report.')
    ap.add_argument('--timeout', type=float, default=45.0)
    args = ap.parse_args()

    h = HardwareManager()
    payload = {
        'schema': 1,
        'generated_at': time.time(),
        'platform': {'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(), 'python': sys.version.split()[0]},
        'hardware': h.status(),
        'candidates': h.candidates(args.workload),
        'placement': None,
    }
    print('=== Hardware inventory ===')
    print(json.dumps(payload['hardware'], indent=2))
    print('\n=== Candidate order ===')
    print(json.dumps(payload['candidates'], indent=2))

    rc = 0
    if args.model:
        model = Path(args.model)
        if not model.is_file():
            raise SystemExit(f'Model does not exist: {model}')
        print('\n=== Real session placement ===')
        try:
            # Prefer the dedicated Windows ML runtime because provider registration
            # is process-local; probe performs ensure/register/session/warm-up in
            # one disposable process. Fall back to in-process ORT for development.
            if h.winml_python and Path(h.winml_python).is_file():
                worker = Path(__file__).resolve().parent / 'winml_worker.py'
                cache = os.environ.get('METATRON_MODEL_CACHE_DIR', '')
                cmd = [h.winml_python, str(worker), '--once', 'probe', '--model', str(model), '--kinds', 'NPU,GPU,CPU']
                if cache:
                    cmd += ['--cache-dir', cache]
                cp = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=args.timeout)
                lines = [x for x in cp.stdout.splitlines() if x.strip()]
                if cp.returncode != 0 or not lines:
                    raise RuntimeError((cp.stderr or cp.stdout or f'probe exited {cp.returncode}')[-2000:])
                actual = json.loads(lines[-1])
                if actual.get('ok') is False:
                    raise RuntimeError(str(actual.get('error')))
            else:
                _session, actual = WindowsMLSessionFactory(h).create_session(
                    str(model), args.workload, require_verified=False
                )
                actual['note'] = 'session created but placement is unverified; configure METATRON_WINML_PYTHON for same-process registration + warm-up proof'
            payload['placement'] = actual
            print(json.dumps(actual, indent=2))
        except Exception as exc:
            payload['placement'] = {'verified': False, 'error': f'{type(exc).__name__}: {exc}'}
            print('FAILED:', payload['placement']['error'])
            rc = 2
    else:
        print('\nNo --model supplied. Inventory/order only; actual placement is UNVERIFIED.')

    if args.report:
        report = Path(args.report)
        _write_report(report, payload)
        print(f'Wrote report: {report}')
        if args.issue_template:
            issue = Path(args.issue_template)
            issue.write_text(_issue_template(report.name), encoding='utf-8')
            print(f'Wrote issue template: {issue}')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
