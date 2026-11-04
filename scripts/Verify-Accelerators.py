from __future__ import annotations

import argparse
import json
from pathlib import Path

from metatron.hardware import HardwareManager, WindowsMLSessionFactory


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect Metatron accelerator routing and optionally compile a real ONNX model.")
    ap.add_argument("--model", help="Optional ONNX model used to prove real NPU -> GPU -> CPU placement.")
    ap.add_argument("--workload", default="verification")
    args = ap.parse_args()

    h = HardwareManager()
    status = h.status()
    print("=== Hardware inventory ===")
    print(json.dumps(status, indent=2))
    print("\n=== Candidate order ===")
    print(json.dumps(h.candidates(args.workload), indent=2))

    if not args.model:
        print("\nNo --model supplied. Inventory/ordering verified only; session placement was not tested.")
        return 0

    model = Path(args.model)
    if not model.is_file():
        raise SystemExit(f"Model does not exist: {model}")
    print("\n=== Real session placement ===")
    try:
        session, actual = WindowsMLSessionFactory(h).create_session(str(model), args.workload)
        print(json.dumps(actual, indent=2))
        print("Providers:", getattr(session, "get_providers", lambda: [])())
        return 0
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
