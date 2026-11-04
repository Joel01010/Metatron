from __future__ import annotations

from metatron.hardware import Accelerator, HardwareManager


class DummyDB:
    def __init__(self): self.data = {}
    def get_setting(self, key, default=None): return self.data.get(key, default)
    def set_setting(self, key, value): self.data[key] = value


def test_policy_is_npu_gpu_cpu_by_default(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [
        Accelerator("n", "NPU", "Any NPU", provider="x"),
        Accelerator("g", "GPU", "Any GPU", provider="y"),
    ])
    m = HardwareManager(DummyDB(), None)
    c = m.candidates("stt")
    assert [x["kind"] for x in c[:3]] == ["NPU", "GPU", "CPU"]


def test_gpu_fallback_when_npu_missing(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [Accelerator("g", "GPU", "GPU", provider="x")])
    m = HardwareManager(DummyDB(), None)
    assert m.select("cleanup")["selected"]["kind"] == "GPU"


def test_actual_device_is_separate_from_requested(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [Accelerator("n", "NPU", "NPU", provider="x")])
    m = HardwareManager(DummyDB(), None)
    assert "stt" not in m.status()["actual"]
    m.report_actual("stt", kind="GPU", provider="fallback", device="GPU.0")
    assert m.status()["actual"]["stt"]["kind"] == "GPU"


def test_all_routable_npus_precede_every_gpu(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [
        Accelerator("n1", "NPU", "NPU One", provider="ep-a", routable=True),
        Accelerator("g1", "GPU", "GPU One", provider="ep-g", routable=True),
        Accelerator("n2", "NPU", "NPU Two", provider="ep-b", routable=True),
        Accelerator("g2", "GPU", "GPU Two", provider="ep-h", routable=True),
    ])
    m = HardwareManager(DummyDB(), None)
    kinds = [x["kind"] for x in m.candidates("stt")]
    assert kinds[:4] == ["NPU", "NPU", "GPU", "GPU"]
    assert kinds[-1] == "CPU"


def test_detected_only_npu_is_not_selected(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [
        Accelerator("n", "NPU", "Device Manager NPU", provider="pnp", routable=False),
        Accelerator("g", "GPU", "Usable GPU", provider="gpu-ep", routable=True),
    ])
    m = HardwareManager(DummyDB(), None)
    selected = m.select("cleanup")["selected"]
    assert selected["kind"] == "GPU"
    st = m.status()
    assert st["counts"]["detected_npu"] == 1
    assert st["counts"]["npu"] == 0


def test_policy_cannot_put_gpu_before_npu(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw, "_openvino_devices", lambda: [])
    monkeypatch.setattr(hw, "_onnxruntime_providers", lambda: [])
    monkeypatch.setattr(hw, "_windows_accelerators", lambda: [
        Accelerator("n", "NPU", "NPU", provider="n"),
        Accelerator("g", "GPU", "GPU", provider="g"),
    ])
    m = HardwareManager(DummyDB(), None)
    m.set_policy(["GPU", "CPU", "NPU"], True)
    assert m.status()["policy"]["order"] == ["NPU", "GPU", "CPU"]
    assert m.select("stt")["selected"]["kind"] == "NPU"


def test_windowsml_session_tries_all_npus_before_gpu(monkeypatch, tmp_path):
    import sys
    import types
    import metatron.hardware as hw

    class T:
        def __init__(self, name): self.name = name
    class HW:
        def __init__(self, kind, name):
            self.type = T(kind); self.name = name; self.vendor = 'test'; self.device_id = name
    class Dev:
        def __init__(self, kind, name, ep): self.hardware_device = HW(kind, name); self.ep_name = ep
    devices = [Dev('NPU','NPU-A','FutureNpuEP'), Dev('NPU','NPU-B','QNNExecutionProvider'), Dev('GPU','GPU-A','DmlExecutionProvider')]
    attempts = []
    class SO:
        def __init__(self): self.dev = None
        def add_provider_for_devices(self, ds, opts): self.dev = ds[0]
    def session(path, sess_options=None, providers=None):
        if sess_options is not None and sess_options.dev is not None:
            attempts.append(sess_options.dev.hardware_device.name)
            if sess_options.dev.hardware_device.name == 'NPU-A':
                raise RuntimeError('unsupported model on first NPU')
            return object()
        raise RuntimeError('unexpected legacy path')
    fake = types.SimpleNamespace(get_ep_devices=lambda: devices, SessionOptions=SO, InferenceSession=session, get_available_providers=lambda: [])
    monkeypatch.setitem(sys.modules, 'onnxruntime', fake)
    monkeypatch.setattr(hw, '_openvino_devices', lambda: [])
    monkeypatch.setattr(hw, '_onnxruntime_providers', lambda: [])
    monkeypatch.setattr(hw, '_windows_accelerators', lambda: [])
    mgr = HardwareManager(DummyDB(), None)
    _, actual = hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'), 'stt')
    assert attempts == ['NPU-A', 'NPU-B']
    assert actual['kind'] == 'NPU'
    assert actual['provider'] == 'QNNExecutionProvider'


def test_windowsml_session_falls_back_to_gpu_after_all_npus_fail(monkeypatch, tmp_path):
    import sys
    import types
    import metatron.hardware as hw

    class T:
        def __init__(self, name): self.name = name
    class HW:
        def __init__(self, kind, name):
            self.type = T(kind); self.name = name; self.vendor = 'test'; self.device_id = name
    class Dev:
        def __init__(self, kind, name, ep): self.hardware_device = HW(kind, name); self.ep_name = ep
    devices = [Dev('NPU','NPU-A','FutureNpuEP'), Dev('NPU','NPU-B','VitisAIExecutionProvider'), Dev('GPU','GPU-A','DmlExecutionProvider')]
    attempts = []
    class SO:
        def __init__(self): self.dev = None
        def add_provider_for_devices(self, ds, opts): self.dev = ds[0]
    def session(path, sess_options=None, providers=None):
        if sess_options is not None and sess_options.dev is not None:
            name = sess_options.dev.hardware_device.name
            attempts.append(name)
            if name.startswith('NPU'):
                raise RuntimeError('NPU compile failed')
            return object()
        raise RuntimeError('unexpected legacy path')
    fake = types.SimpleNamespace(get_ep_devices=lambda: devices, SessionOptions=SO, InferenceSession=session, get_available_providers=lambda: [])
    monkeypatch.setitem(sys.modules, 'onnxruntime', fake)
    monkeypatch.setattr(hw, '_openvino_devices', lambda: [])
    monkeypatch.setattr(hw, '_onnxruntime_providers', lambda: [])
    monkeypatch.setattr(hw, '_windows_accelerators', lambda: [])
    mgr = HardwareManager(DummyDB(), None)
    _, actual = hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'), 'cleanup')
    assert attempts == ['NPU-A', 'NPU-B', 'GPU-A']
    assert actual['kind'] == 'GPU'
    assert actual['provider'] == 'DmlExecutionProvider'


def test_legacy_openvino_is_explicitly_pinned_by_class(monkeypatch, tmp_path):
    import sys
    import types
    import metatron.hardware as hw

    attempts = []
    def session(path, sess_options=None, providers=None):
        ep = providers[0]
        if isinstance(ep, tuple):
            name, opts = ep
        else:
            name, opts = ep, {}
        attempts.append((name, dict(opts)))
        if opts.get('device_type') == 'NPU':
            raise RuntimeError('NPU unsupported')
        if opts.get('device_type') == 'GPU':
            return object()
        raise RuntimeError('unexpected')
    fake = types.SimpleNamespace(
        get_available_providers=lambda: ['OpenVINOExecutionProvider','CPUExecutionProvider'],
        InferenceSession=session,
    )
    monkeypatch.setitem(sys.modules, 'onnxruntime', fake)
    monkeypatch.setattr(hw, '_openvino_devices', lambda: [])
    monkeypatch.setattr(hw, '_onnxruntime_providers', lambda: [])
    monkeypatch.setattr(hw, '_windows_accelerators', lambda: [])
    mgr = HardwareManager(DummyDB(), None)
    _, actual = hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'), 'cleanup')
    assert attempts[:2] == [
        ('OpenVINOExecutionProvider', {'device_type':'NPU'}),
        ('OpenVINOExecutionProvider', {'device_type':'GPU'}),
    ]
    assert actual['kind'] == 'GPU'
