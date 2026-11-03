"""Probe the official Orukeet INT8 ONNX encoder on Intel NPU.

This is intentionally strict:
- OpenVINO must expose NPU.
- The encoder graph must be read by OpenVINO.
- The entire encoder must compile for device="NPU".
- No AUTO/CPU fallback is used.

A compile failure is evidence that more export/reshape work is needed; it is
not hidden by switching devices.
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import time

try:
    import openvino as ov
except Exception as e:
    print("ERROR: OpenVINO import failed:", e)
    sys.exit(2)

def describe(model):
    print("Inputs:")
    for i in model.inputs:
        names = sorted(i.get_names())
        print(" ", names or ["<unnamed>"], i.get_partial_shape(), i.get_element_type())
    print("Outputs:")
    for o in model.outputs:
        names = sorted(o.get_names())
        print(" ", names or ["<unnamed>"], o.get_partial_shape(), o.get_element_type())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", type=Path, default=Path("orukeet-model"))
    ap.add_argument("--cache-dir", type=Path, default=Path("orukeet-npu-cache"))
    args = ap.parse_args()

    enc = args.model_dir / "encoder.int8.onnx"
    if not enc.exists():
        print("ERROR: missing", enc)
        print("Run download_orukeet_onnx.py first.")
        sys.exit(3)

    core = ov.Core()
    print("OpenVINO:", getattr(ov, "__version__", "unknown"))
    print("Available devices:", core.available_devices)
    if "NPU" not in core.available_devices:
        print("FAIL: NPU not available to OpenVINO.")
        sys.exit(4)

    try:
        print("NPU:", core.get_property("NPU", "FULL_DEVICE_NAME"))
        print("NPU driver:", core.get_property("NPU", "NPU_DRIVER_VERSION"))
    except Exception as e:
        print("NPU property query note:", e)

    print("\nReading encoder:", enc)
    model = core.read_model(str(enc))
    describe(model)

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    props = {
        "CACHE_DIR": str(args.cache_dir.resolve()),
        "PERFORMANCE_HINT": "LATENCY",
    }

    print("\nCompiling ENTIRE encoder directly for NPU...")
    t0 = time.perf_counter()
    try:
        compiled = core.compile_model(model, "NPU", props)
    except Exception as e:
        print("\nFAIL: encoder did not fully compile on Intel NPU.")
        print(type(e).__name__ + ":", e)
        print("\nThis is still useful: the agent should now inspect the input shapes")
        print("and apply the same static-window reshape/export strategy used by")
        print("Parakeet-v3 OpenVINO implementations such as eddy-audio.")
        sys.exit(5)

    dt = time.perf_counter() - t0
    print(f"\nPASS: complete Orukeet encoder compiled for NPU in {dt:.2f}s.")
    try:
        print("Execution devices:", compiled.get_property("EXECUTION_DEVICES"))
    except Exception:
        pass
    print("This passes the NPU compilation gate, but a real transcription")
    print("benchmark is still required before promoting Orukeet to production.")

if __name__ == "__main__":
    main()
