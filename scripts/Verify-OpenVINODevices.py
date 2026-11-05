#!/usr/bin/env python3
"""Direct Intel OpenVINO device proof for Metatron qualification.

Uses the same public pattern documented by OpenVINO: create a Core, build a tiny
static model, compile it explicitly for each requested device, then execute a
real inference. A device is PASS only after compile + infer succeeds.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path


def write(path: str, payload: dict) -> None:
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devices", default="NPU,GPU,CPU", help="Ordered device list")
    ap.add_argument("--require", default="", help="Comma-separated devices that must PASS")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()
    try:
        import numpy as np
        import openvino as ov
        from openvino import opset13 as ops
    except Exception as exc:
        out = {"schema": 1, "version": "1.4.0", "status": "SKIP", "reason": f"OpenVINO unavailable: {type(exc).__name__}: {exc}"}
        write(args.json_out, out)
        print(json.dumps(out, indent=2))
        return 3

    core = ov.Core()
    available = list(core.available_devices)
    requested = [x.strip().upper() for x in args.devices.split(",") if x.strip()]
    required = {x.strip().upper() for x in args.require.split(",") if x.strip()}

    # Small static graph intentionally avoids model-download/network dependencies.
    # It validates the device plugin/compiler/execution path, not model compatibility.
    param = ops.parameter([1, 256], ov.Type.f32, name="input")
    bias = ops.constant(np.linspace(-0.5, 0.5, 256, dtype=np.float32).reshape(1, 256))
    result = ops.result(ops.relu(ops.add(param, bias)))
    model = ov.Model([result], [param], "metatron_device_probe")
    sample = np.ones((1, 256), dtype=np.float32)

    rows = []
    for device in requested:
        row = {"device": device, "available": any(d == device or d.startswith(device + ".") for d in available), "verified": False}
        if not row["available"]:
            row["status"] = "UNAVAILABLE"
            rows.append(row)
            continue
        try:
            t0 = time.perf_counter()
            compiled = core.compile_model(model, device)
            row["compile_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            t1 = time.perf_counter()
            output = compiled([sample])[compiled.output(0)]
            row["infer_ms"] = round((time.perf_counter() - t1) * 1000, 2)
            row["verified"] = bool(output.shape == (1, 256) and np.isfinite(output).all())
            row["status"] = "PASS" if row["verified"] else "FAIL"
            try:
                row["execution_devices"] = list(compiled.get_property("EXECUTION_DEVICES"))
            except Exception:
                pass
        except Exception as exc:
            row["status"] = "FAIL"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)

    passed = {r["device"] for r in rows if r.get("verified")}
    missing_required = sorted(required - passed)
    out = {
        "schema": 1,
        "version": "1.4.0",
        "platform": {"system": platform.system(), "release": platform.release(), "python": sys.version.split()[0]},
        "openvino_version": getattr(ov, "__version__", None),
        "available_devices": available,
        "results": rows,
        "required": sorted(required),
        "missing_required": missing_required,
        "status": "PASS" if not missing_required else "FAIL",
        "note": "This proves OpenVINO device compile+infer. Application-model compatibility is qualified separately.",
    }
    write(args.json_out, out)
    print(json.dumps(out, indent=2))
    return 0 if not missing_required else 2


if __name__ == "__main__":
    raise SystemExit(main())
