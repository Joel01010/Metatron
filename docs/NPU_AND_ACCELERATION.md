# NPU and accelerator architecture

## Policy

Metatron's default policy is explicit:

1. **Every routable NPU** exposed by Windows ML/OpenVINO
2. **Every routable GPU** exposed by an installed execution provider
3. CPU

A requested device is not the same as an actual device. The UI shows runtime placement only after the model/session successfully reports it. A PnP-detected accelerator without a usable execution provider is shown as **detected only** and is never selected for inference.

## Windows ML path

On current Windows ML 2.x, ONNX Runtime exposes execution-provider devices with a hardware type. Metatron's `WindowsMLSessionFactory` uses those concrete EP-device objects rather than inferring hardware from provider names.

Supported NPU families depend on Windows/driver compatibility and the installed Windows-certified execution providers. Current Windows ML documentation maps:

- Intel NPU -> OpenVINOExecutionProvider
- Qualcomm NPU -> QNNExecutionProvider
- AMD NPU -> VitisAIExecutionProvider

GPU providers may include Intel OpenVINO, NVIDIA NvTensorRtRtx, AMD MIGraphX, Qualcomm QNN, and DirectML fallback.

References:

- https://learn.microsoft.com/windows/ai/new-windows-ml/accelerate-ai-models
- https://learn.microsoft.com/windows/ai/new-windows-ml/supported-execution-providers
- https://learn.microsoft.com/windows/ai/new-windows-ml/select-execution-providers
- https://learn.microsoft.com/windows/ai/new-windows-ml/distributing-your-app

## Why not bare OpenVINO AUTO?

OpenVINO's current automatic device selection excludes NPU from its default priority list. The direct OpenVINO helper in Metatron therefore iterates explicit NPU devices, then GPU, then CPU.

Reference:

- https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/auto-device-selection.html

## Windows ML runtime isolation

The main Metatron backend intentionally has no heavyweight ML dependency. `scripts/Setup-WindowsML.ps1` creates a separate Python environment containing:

- wasdk-Microsoft.Windows.AI.MachineLearning[all]
- wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap
- onnxruntime-windowsml

This lets Metatron terminate/replace ML workers without leaving ONNX/OpenVINO heaps resident in its control plane.

## Execution provider acquisition

`scripts/winml_worker.py` can enumerate compatible providers and call `ensure_ready_async()` for user-approved provider downloads. It then registers ready provider libraries with ONNX Runtime and enumerates `get_ep_devices()`.

The user should initiate downloads from the Hardware page. Metatron does not silently download vendor runtimes at startup.

## Fallback semantics

When a workload starts:

```text
for class in [NPU, GPU, CPU]:
    for real device of that class:
        try to create/compile model session
        if successful:
            report_actual(workload, class, provider, device)
            use it
```

Failures continue to the next device. If all candidates fail, Metatron reports the collected errors rather than lying about a fallback.

## Intel direct path

If OpenVINO is installed directly, `OpenVINOCompiler` uses `ov.Core().available_devices` and explicitly compiles to `NPU*`, `GPU*`, then `CPU*`. This path is useful for Intel-specific OpenVINO models and existing NPU pipelines.

## Tests expected on release hardware

A release should validate:

- accelerator enumeration
- real model compile/session creation
- actual placement reporting
- NPU failure -> GPU success
- NPU+GPU failure -> CPU success
- no silent fallback claim
- worker shutdown actually frees process-tree memory
- device loss / driver reset is surfaced and retriable

## Cross-vendor guarantee

Metatron does not hard-code an Intel-only NPU list. On modern Windows ML builds, any execution-provider device whose hardware type is reported as `NPU` is automatically placed in the NPU candidate class, including future certified providers that did not exist when this release was built. Known current mappings include Intel/OpenVINO, Qualcomm/QNN and AMD/VitisAI.

The class order is a product invariant: user settings cannot place GPU or CPU ahead of NPU. If every NPU session/compile attempt fails, Metatron tries all routable GPU candidates. CPU is the final optional fallback.

Legacy ONNX Runtime builds without EP-device enumeration use explicit class-specific attempts. OpenVINO is pinned with `device_type=NPU`, then `device_type=GPU`, then `device_type=CPU`; provider-name availability alone is never treated as proof that OpenVINO is running on an NPU.
