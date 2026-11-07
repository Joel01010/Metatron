#!/usr/bin/env python3
"""Generate Metatron's tiny self-contained ONNX accelerator probe model.

This file exists so Windows qualification never depends on a human supplying a
model path. The graph is intentionally tiny and deterministic: float32 input
[1,256] -> Add(constant bias) -> Relu -> output [1,256].
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    try:
        import numpy as np
        import onnx
        from onnx import TensorProto, helper, numpy_helper
    except Exception as exc:
        raise SystemExit(f"onnx/numpy unavailable: {type(exc).__name__}: {exc}")

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    inp = helper.make_tensor_value_info("input", TensorProto.FLOAT, [1, 256])
    output = helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, 256])
    bias = np.linspace(-0.5, 0.5, 256, dtype=np.float32).reshape(1, 256)
    bias_init = numpy_helper.from_array(bias, name="bias")
    nodes = [
        helper.make_node("Add", ["input", "bias"], ["sum"]),
        helper.make_node("Relu", ["sum"], ["output"]),
    ]
    graph = helper.make_graph(nodes, "metatron_probe", [inp], [output], [bias_init])
    model = helper.make_model(
        graph,
        producer_name="metatron-qualification",
        opset_imports=[helper.make_opsetid("", 13)],
    )
    model.ir_version = min(model.ir_version, 10)
    onnx.checker.check_model(model)
    onnx.save(model, out)
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
