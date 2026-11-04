from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class Accelerator:
    id: str
    kind: str  # NPU | GPU | CPU
    name: str
    vendor: str = "unknown"
    provider: str = "system"
    provider_device: str = ""
    source: str = "system"
    available: bool = True
    routable: bool = True
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["details"] = dict(self.details or {})
        return d


@dataclass(slots=True)
class DeviceSelection:
    workload: str
    requested_order: list[str]
    selected: dict[str, Any]
    candidates: list[dict[str, Any]]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_VENDOR_PATTERNS = (
    ("intel", re.compile(r"intel|arc|uhd|iris|ai boost", re.I)),
    ("amd", re.compile(r"amd|radeon|ryzen ai|vitis", re.I)),
    ("qualcomm", re.compile(r"qualcomm|snapdragon|hexagon", re.I)),
    ("nvidia", re.compile(r"nvidia|geforce|quadro|rtx", re.I)),
)

_NPU_PATTERNS = re.compile(
    r"\bNPU\b|neural processing|neural processor|AI Boost|Ryzen AI|Hexagon|VitisAI|Neural Compute",
    re.I,
)


def _vendor(name: str) -> str:
    for vendor, pattern in _VENDOR_PATTERNS:
        if pattern.search(name or ""):
            return vendor
    return "unknown"


def _run_json_powershell(script: str, timeout: float = 4.0) -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        return []
    try:
        cp = subprocess.run(
            [shell, "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if cp.returncode != 0 or not cp.stdout.strip():
            return []
        data = json.loads(cp.stdout)
        if isinstance(data, dict):
            return [data]
        return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []
    except Exception:
        return []


def _windows_accelerators() -> list[Accelerator]:
    # PnP discovery intentionally uses broad naming instead of vendor IDs. New
    # NPU vendors can therefore appear without a Metatron release.
    script = r'''
$items = Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '(?i)NPU|Neural|AI Boost|Ryzen AI|Hexagon|Vitis' } |
  Select-Object Name,Manufacturer,PNPDeviceID,Status
$gpus = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue |
  Select-Object Name,AdapterCompatibility,PNPDeviceID,DriverVersion,AdapterRAM,Status
@{ npu = @($items); gpu = @($gpus) } | ConvertTo-Json -Depth 4 -Compress
'''
    rows = _run_json_powershell(script)
    if not rows:
        return []
    root = rows[0]
    out: list[Accelerator] = []
    for idx, item in enumerate(root.get("npu") or []):
        name = str(item.get("Name") or "NPU")
        if not _NPU_PATTERNS.search(name):
            continue
        manufacturer = str(item.get("Manufacturer") or "")
        out.append(Accelerator(
            id=f"win-npu-{idx}", kind="NPU", name=name,
            vendor=_vendor(name + " " + manufacturer), provider="windows-hardware",
            provider_device=str(item.get("PNPDeviceID") or ""), source="windows-pnp",
            available=str(item.get("Status") or "OK").lower() not in {"error", "degraded"},
            routable=False,
            details={"manufacturer": manufacturer, "status": item.get("Status"), "note": "hardware detected; install a compatible execution provider to route workloads"},
        ))
    for idx, item in enumerate(root.get("gpu") or []):
        name = str(item.get("Name") or "GPU")
        compat = str(item.get("AdapterCompatibility") or "")
        out.append(Accelerator(
            id=f"win-gpu-{idx}", kind="GPU", name=name,
            vendor=_vendor(name + " " + compat), provider="windows-hardware",
            provider_device=str(item.get("PNPDeviceID") or ""), source="windows-video",
            available=str(item.get("Status") or "OK").lower() not in {"error", "degraded"},
            routable=False,
            details={"driver": item.get("DriverVersion"), "adapter_ram": item.get("AdapterRAM"), "compatibility": compat, "note": "hardware detected; runtime provider required for routing"},
        ))
    return out


def _openvino_devices() -> list[Accelerator]:
    try:
        import openvino as ov  # type: ignore
    except Exception:
        return []
    try:
        core = ov.Core()
        out: list[Accelerator] = []
        for dev in core.available_devices:
            upper = str(dev).upper()
            if upper.startswith("NPU"):
                kind = "NPU"
            elif upper.startswith("GPU"):
                kind = "GPU"
            elif upper.startswith("CPU"):
                kind = "CPU"
            else:
                continue
            name = str(dev)
            details: dict[str, Any] = {}
            try:
                full = core.get_property(dev, "FULL_DEVICE_NAME")
                if full:
                    name = str(full)
            except Exception:
                pass
            for prop in ("DEVICE_UUID", "DEVICE_ARCHITECTURE", "SUPPORTED_PROPERTIES"):
                try:
                    val = core.get_property(dev, prop)
                    if prop != "SUPPORTED_PROPERTIES":
                        details[prop.lower()] = str(val)
                except Exception:
                    pass
            out.append(Accelerator(
                id=f"openvino:{dev}", kind=kind, name=name, vendor="intel",
                provider="OpenVINOExecutionProvider", provider_device=str(dev),
                source="openvino", available=True, details=details,
            ))
        return out
    except Exception:
        return []


# Windows ML certified execution provider names. They are kept as metadata even
# if Python cannot currently enumerate the Windows EP catalog directly. If an EP
# is installed into ONNX Runtime, it is surfaced below and becomes routable.
_EP_CLASS: dict[str, tuple[str, str]] = {
    "QNNExecutionProvider": ("NPU", "qualcomm"),
    "VitisAIExecutionProvider": ("NPU", "amd"),
    "OpenVINOExecutionProvider": ("NPU", "intel"),
    "NvTensorRtRtxExecutionProvider": ("GPU", "nvidia"),
    "MIGraphXExecutionProvider": ("GPU", "amd"),
    "DmlExecutionProvider": ("GPU", "microsoft"),
    "CUDAExecutionProvider": ("GPU", "nvidia"),
    "ROCMExecutionProvider": ("GPU", "amd"),
    "CPUExecutionProvider": ("CPU", "generic"),
}


def _ort_kind(value: Any) -> str:
    raw = str(getattr(value, "name", value)).upper()
    if "NPU" in raw:
        return "NPU"
    if "GPU" in raw:
        return "GPU"
    if "CPU" in raw:
        return "CPU"
    return "OTHER"


def _onnxruntime_providers() -> list[Accelerator]:
    """Enumerate Windows ML / ONNX Runtime EP devices when available.

    Windows ML 2.x exposes ``onnxruntime.get_ep_devices()``. Unlike the older
    provider-name list, every returned device has a real hardware type, so an
    OpenVINO EP can be correctly distinguished as NPU vs GPU vs CPU and any
    future certified NPU EP becomes automatically routable.
    """
    try:
        import onnxruntime as ort  # type: ignore
    except Exception:
        return []
    out: list[Accelerator] = []
    get_devices = getattr(ort, "get_ep_devices", None)
    if callable(get_devices):
        try:
            for idx, d in enumerate(get_devices()):
                kind = _ort_kind(getattr(getattr(d, "hardware_device", None), "type", ""))
                if kind not in {"NPU", "GPU", "CPU"}:
                    continue
                ep = str(getattr(d, "ep_name", "") or "UnknownExecutionProvider")
                hw = getattr(d, "hardware_device", None)
                name = str(getattr(hw, "name", "") or getattr(hw, "vendor", "") or ep)
                vendor = _EP_CLASS.get(ep, (kind, _vendor(name)))[1]
                details = {
                    "device_type": kind,
                    "hardware_name": name,
                    "hardware_vendor": str(getattr(hw, "vendor", "") or ""),
                    "device_id": str(getattr(hw, "device_id", "") or ""),
                }
                out.append(Accelerator(
                    id=f"winml:{ep}:{kind}:{idx}", kind=kind,
                    name=f"{name} ({ep})" if name != ep else ep,
                    vendor=vendor, provider=ep, provider_device=str(idx),
                    source="windows-ml", available=True, details=details,
                ))
            if out:
                return out
        except Exception:
            pass
    # Compatibility path for ordinary ONNX Runtime packages without Windows ML
    # EP device enumeration. This can identify provider availability but cannot
    # prove which OpenVINO hardware target a session will use.
    try:
        providers = ort.get_available_providers()
    except Exception:
        return []
    for ep in providers:
        kind, vendor = _EP_CLASS.get(str(ep), ("OTHER", "unknown"))
        if kind == "OTHER":
            continue
        details: dict[str, Any] = {"legacy_provider_enumeration": True}
        # A provider name alone is not enough to prove OpenVINO hardware class.
        # Keep it visible in inventory but do not route through this pseudo-device;
        # direct OpenVINO discovery or an explicit provider option is used instead.
        if ep == "OpenVINOExecutionProvider":
            details["targets"] = ["NPU", "GPU", "CPU"]
            out.append(Accelerator(
                id=f"ort:{ep}", kind="PROVIDER", name=str(ep), vendor=vendor,
                provider=str(ep), provider_device="", source="onnxruntime",
                available=True, routable=False, details=details,
            ))
            continue
        out.append(Accelerator(
            id=f"ort:{ep}", kind=kind, name=str(ep), vendor=vendor,
            provider=str(ep), provider_device="", source="onnxruntime",
            available=True, routable=True, details=details,
        ))
    return out

def _cpu_device() -> Accelerator:
    return Accelerator(
        id="cpu:system", kind="CPU", name=platform.processor() or platform.machine() or "CPU",
        vendor=_vendor(platform.processor()), provider="CPUExecutionProvider",
        source="python", available=True, details={"machine": platform.machine()},
    )


class HardwareManager:
    """Cross-vendor accelerator discovery and NPU -> GPU -> CPU policy.

    Metatron never reports a requested accelerator as the *actual* accelerator.
    A worker must call ``report_actual`` after successful model/session creation.
    This distinction prevents misleading UI such as "NPU active" when a runtime
    silently fell back to CPU.
    """

    def __init__(self, db: Any | None = None, bus: Any | None = None, winml_python: str = ""):
        self.db = db
        self.bus = bus
        self._lock = threading.RLock()
        self.winml_python = str(winml_python or os.environ.get("METATRON_WINML_PYTHON", ""))
        self._devices: list[Accelerator] = []
        self._last_refresh = 0.0
        self._actual: dict[str, dict[str, Any]] = {}
        saved = db.get_setting("hardware.policy", {}) if db is not None else {}
        if not isinstance(saved, dict):
            saved = {}
        # Hardware-class order is intentionally fixed: every usable NPU first,
        # then every usable GPU, then CPU. Provider/device ordering inside a class
        # remains dynamic so all present and future NPUs are eligible.
        self._order = ["NPU", "GPU", "CPU"]
        self._allow_cpu = bool(saved.get("allow_cpu", True))
        self.refresh()

    @staticmethod
    def _normalize_order(order: Iterable[str]) -> list[str]:
        clean: list[str] = []
        for raw in order:
            value = str(raw).upper()
            if value in {"NPU", "GPU", "CPU"} and value not in clean:
                clean.append(value)
        for value in ("NPU", "GPU", "CPU"):
            if value not in clean:
                clean.append(value)
        return clean


    def _winml_worker(self, command: str, names: list[str] | None = None, timeout: float = 180.0) -> dict[str, Any]:
        py = self.winml_python
        if not py or not Path(py).is_file():
            return {"configured": False, "error": "Windows ML runtime is not configured. Run scripts/Setup-WindowsML.ps1."}
        worker = Path(__file__).resolve().parents[1] / "scripts" / "winml_worker.py"
        if not worker.is_file():
            return {"configured": False, "error": "winml_worker.py is missing"}
        args = [py, str(worker), "--once", command]
        if names:
            args += ["--names", ",".join(names)]
        try:
            cp = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            lines = [x for x in cp.stdout.splitlines() if x.strip()]
            if not lines:
                return {"configured": True, "error": (cp.stderr or f"worker exited {cp.returncode}")[-1200:]}
            data = json.loads(lines[-1])
            if isinstance(data, dict) and data.get("ok") is False:
                return {"configured": True, "error": str(data.get("error") or data)}
            return {"configured": True, **(data if isinstance(data, dict) else {"result": data})}
        except Exception as exc:
            return {"configured": True, "error": f"{type(exc).__name__}: {exc}"}

    def windows_ml_catalog(self) -> dict[str, Any]:
        return self._winml_worker("catalog", timeout=20.0)

    def ensure_windows_ml_providers(self, names: list[str] | None = None) -> dict[str, Any]:
        result = self._winml_worker("ensure", names=names, timeout=600.0)
        # A successful install changes the system EP set. Refresh hardware after
        # the worker exits so PnP/OpenVINO changes are reflected immediately.
        try:
            self.refresh()
        except Exception:
            pass
        if self.bus is not None:
            self.bus.emit("hardware.windows_ml.ensure", "user", {"ok": not bool(result.get("error")), "names": names or []})
        return result

    def refresh(self) -> dict[str, Any]:
        found = _openvino_devices() + _onnxruntime_providers() + _windows_accelerators()
        found.append(_cpu_device())
        dedup: dict[tuple[str, str, str], Accelerator] = {}
        for d in found:
            key = (d.kind, d.provider, d.provider_device or d.name)
            prev = dedup.get(key)
            # Prefer a runtime-visible device over a pure hardware listing.
            if prev is None or (prev.source.startswith("windows") and not d.source.startswith("windows")):
                dedup[key] = d
        with self._lock:
            self._devices = list(dedup.values())
            self._last_refresh = time.time()
        if self.bus is not None:
            self.bus.emit("hardware.refreshed", "hardware", {
                "npus": sum(1 for x in self._devices if x.kind == "NPU" and x.available),
                "gpus": sum(1 for x in self._devices if x.kind == "GPU" and x.available),
            })
        return self.status()

    def set_policy(self, order: Iterable[str] | None = None, allow_cpu: bool = True) -> dict[str, Any]:
        # NPU -> GPU -> CPU is a product invariant. We retain the argument for
        # protocol compatibility but never permit GPU/CPU to leapfrog an NPU.
        normalized = ["NPU", "GPU", "CPU"]
        with self._lock:
            self._order = normalized
            self._allow_cpu = bool(allow_cpu)
        if self.db is not None:
            self.db.set_setting("hardware.policy", {"order": normalized, "allow_cpu": bool(allow_cpu)})
        if self.bus is not None:
            self.bus.emit("hardware.policy", "user", {"order": normalized, "allow_cpu": bool(allow_cpu)})
        return self.status()

    def candidates(self, workload: str = "generic", order: Iterable[str] | None = None) -> list[dict[str, Any]]:
        requested = self._normalize_order(order or self._order)
        with self._lock:
            devices = [x for x in self._devices if x.available and x.routable]
        ranked: list[Accelerator] = []
        for kind in requested:
            if kind == "CPU" and not self._allow_cpu:
                continue
            for d in devices:
                if d.kind == kind and d not in ranked:
                    ranked.append(d)
        if self._allow_cpu and not any(d.kind == "CPU" for d in ranked):
            ranked.append(_cpu_device())
        return [d.to_dict() for d in ranked]

    def select(self, workload: str = "generic", order: Iterable[str] | None = None) -> dict[str, Any]:
        requested = self._normalize_order(order or self._order)
        candidates = self.candidates(workload, requested)
        if not candidates:
            raise RuntimeError("no usable accelerator found")
        chosen = candidates[0]
        return DeviceSelection(
            workload=workload, requested_order=requested, selected=chosen,
            candidates=candidates,
            reason=f"first available device in {' > '.join(requested)} policy",
        ).to_dict()

    def report_actual(self, workload: str, *, kind: str, provider: str, device: str = "", model: str = "") -> dict[str, Any]:
        record = {
            "workload": str(workload), "kind": str(kind).upper(), "provider": str(provider),
            "device": str(device), "model": str(model), "ts": time.time(),
        }
        with self._lock:
            self._actual[str(workload)] = record
        if self.bus is not None:
            self.bus.emit("hardware.actual_device", "runtime", record)
        return record

    def status(self) -> dict[str, Any]:
        with self._lock:
            devices = [d.to_dict() for d in self._devices]
            actual = dict(self._actual)
            order = list(self._order)
            last = self._last_refresh
        return {
            "policy": {"order": order, "allow_cpu": self._allow_cpu},
            "devices": devices,
            "counts": {
                "npu": sum(1 for d in devices if d["kind"] == "NPU" and d["available"] and d.get("routable", True)),
                "gpu": sum(1 for d in devices if d["kind"] == "GPU" and d["available"] and d.get("routable", True)),
                "cpu": sum(1 for d in devices if d["kind"] == "CPU" and d["available"] and d.get("routable", True)),
                "detected_npu": sum(1 for d in devices if d["kind"] == "NPU" and d["available"]),
                "detected_gpu": sum(1 for d in devices if d["kind"] == "GPU" and d["available"]),
            },
            "actual": actual,
            "last_refresh": last,
        }


class WindowsMLSessionFactory:
    """Create ONNX Runtime sessions using an explicit NPU -> GPU -> CPU policy.

    On Windows ML 2.x this uses real EpDevice objects. No device is reported as
    active until session construction succeeds. It supports Intel/OpenVINO,
    Qualcomm/QNN, AMD/VitisAI and future NPU EPs exposed by Windows ML without
    vendor-specific branching in Metatron.
    """

    def __init__(self, hardware: HardwareManager):
        self.hardware = hardware

    def create_session(
        self, model_path: str, workload: str, *, provider_options: dict[str, dict[str, str]] | None = None
    ) -> tuple[Any, dict[str, Any]]:
        try:
            import onnxruntime as ort  # type: ignore
        except Exception as exc:
            raise RuntimeError("ONNX Runtime / Windows ML is not installed") from exc
        provider_options = provider_options or {}
        errors: list[str] = []
        get_devices = getattr(ort, "get_ep_devices", None)
        if callable(get_devices):
            try:
                devices = list(get_devices())
            except Exception:
                devices = []
            order = self.hardware.status()["policy"]["order"]
            for kind in order:
                for d in devices:
                    if _ort_kind(getattr(getattr(d, "hardware_device", None), "type", "")) != kind:
                        continue
                    ep = str(getattr(d, "ep_name", "") or "")
                    try:
                        opts = ort.SessionOptions()
                        add = getattr(opts, "add_provider_for_devices", None)
                        if not callable(add):
                            raise RuntimeError("Windows ML device API is unavailable in this ONNX Runtime build")
                        add([d], provider_options.get(ep, {}))
                        session = ort.InferenceSession(str(model_path), sess_options=opts)
                        actual = self.hardware.report_actual(
                            workload, kind=kind, provider=ep,
                            device=str(getattr(getattr(d, "hardware_device", None), "name", "") or d),
                            model=str(model_path),
                        )
                        return session, actual
                    except Exception as exc:
                        errors.append(f"{kind}/{ep}: {type(exc).__name__}: {exc}")
        # Legacy provider fallback. Explicit class pinning preserves the same
        # NPU -> GPU -> CPU contract even when Windows ML EpDevice enumeration
        # is unavailable. Unknown future EPs become fully generic once they
        # expose EpDevices through Windows ML.
        try:
            available = list(ort.get_available_providers())
        except Exception:
            available = []
        class_attempts: dict[str, list[tuple[str, dict[str, str]]]] = {
            "NPU": [
                ("QNNExecutionProvider", {}),
                ("VitisAIExecutionProvider", {}),
                ("OpenVINOExecutionProvider", {"device_type": "NPU"}),
            ],
            "GPU": [
                ("NvTensorRtRtxExecutionProvider", {}),
                ("MIGraphXExecutionProvider", {}),
                ("CUDAExecutionProvider", {}),
                ("ROCMExecutionProvider", {}),
                ("DmlExecutionProvider", {}),
                ("OpenVINOExecutionProvider", {"device_type": "GPU"}),
            ],
            "CPU": [
                ("CPUExecutionProvider", {}),
                ("OpenVINOExecutionProvider", {"device_type": "CPU"}),
            ],
        }
        order = self.hardware.status()["policy"]["order"]
        allow_cpu = bool(self.hardware.status()["policy"].get("allow_cpu", True))
        for kind in order:
            if kind == "CPU" and not allow_cpu:
                continue
            for ep, defaults in class_attempts.get(kind, []):
                if ep not in available:
                    continue
                options = dict(defaults)
                options.update(provider_options.get(ep, {}))
                try:
                    provider_spec: Any = (ep, options) if options else ep
                    session = ort.InferenceSession(str(model_path), providers=[provider_spec])
                    # Session creation succeeded with an explicit device-class
                    # target (or a class-specific EP), so this placement is real.
                    actual = self.hardware.report_actual(
                        workload, kind=kind, provider=ep,
                        device=options.get("device_type", "legacy"), model=str(model_path),
                    )
                    return session, actual
                except Exception as exc:
                    errors.append(f"legacy/{kind}/{ep}: {type(exc).__name__}: {exc}")
        raise RuntimeError("No Windows ML/ORT device could create the session: " + " | ".join(errors[-8:]))


class OpenVINOCompiler:
    """Small helper that explicitly tries NPU, then GPU, then CPU.

    It intentionally does not use bare OpenVINO ``AUTO`` because NPU is not in
    OpenVINO's default AUTO priority list. Workers can use this helper and then
    call ``HardwareManager.report_actual`` after successful compilation.
    """

    def __init__(self, hardware: HardwareManager):
        self.hardware = hardware

    def compile(self, model: Any, workload: str, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        try:
            import openvino as ov  # type: ignore
        except Exception as exc:
            raise RuntimeError("OpenVINO is not installed") from exc
        core = ov.Core()
        errors: list[str] = []
        available = list(core.available_devices)
        order = self.hardware.status()["policy"]["order"]
        for kind in order:
            names = [x for x in available if str(x).upper().startswith(kind)]
            for dev in names:
                try:
                    compiled = core.compile_model(model, str(dev), config or {})
                    actual = self.hardware.report_actual(
                        workload, kind=kind, provider="OpenVINO", device=str(dev),
                        model=getattr(model, "friendly_name", ""),
                    )
                    return compiled, actual
                except Exception as exc:
                    errors.append(f"{dev}: {type(exc).__name__}: {exc}")
        raise RuntimeError("OpenVINO compilation failed on all NPU/GPU/CPU candidates: " + " | ".join(errors[-6:]))
