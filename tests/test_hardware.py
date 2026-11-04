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


def test_fault_injection_exhausts_npus_before_gpu(monkeypatch, tmp_path):
    import sys, types
    import metatron.hardware as hw
    class T:
        def __init__(self, name): self.name=name
    class H:
        def __init__(self, kind, name): self.type=T(kind); self.name=name
    class D:
        def __init__(self, kind, name, ep): self.hardware_device=H(kind,name); self.ep_name=ep
    devices=[D('NPU','NPU-A','EP-A'),D('NPU','NPU-B','EP-B'),D('GPU','GPU-A','EP-G')]
    attempts=[]
    class SO:
        def __init__(self): self.dev=None; self.cfg={}
        def add_session_config_entry(self,k,v): self.cfg[k]=v
        def add_provider_for_devices(self, ds, opts): self.dev=ds[0]
    def session(path,sess_options=None,providers=None):
        attempts.append(sess_options.dev.hardware_device.name); return object()
    fake=types.SimpleNamespace(get_ep_devices=lambda:devices,SessionOptions=SO,InferenceSession=session,get_available_providers=lambda:[])
    monkeypatch.setitem(sys.modules,'onnxruntime',fake)
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[]); monkeypatch.setattr(hw,'_windows_accelerators',lambda:[])
    mgr=HardwareManager(DummyDB(),None,fault_injector=lambda d,w: d['kind']=='NPU')
    _, actual=hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'),'verify')
    assert attempts == ['GPU-A']  # rejected NPUs never reach session construction
    assert actual['kind']=='GPU'


def test_session_created_is_not_recorded_as_actual_without_warmup(monkeypatch, tmp_path):
    import sys, types
    import metatron.hardware as hw
    class T:
        def __init__(self,name): self.name=name
    class H:
        def __init__(self): self.type=T('GPU'); self.name='GPU-A'
    class D:
        hardware_device=H(); ep_name='DmlExecutionProvider'
    class SO:
        def add_session_config_entry(self,k,v): pass
        def add_provider_for_devices(self,ds,opts): pass
    fake=types.SimpleNamespace(get_ep_devices=lambda:[D()],SessionOptions=SO,InferenceSession=lambda *a,**k:object(),get_available_providers=lambda:[])
    monkeypatch.setitem(sys.modules,'onnxruntime',fake)
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[]); monkeypatch.setattr(hw,'_windows_accelerators',lambda:[])
    mgr=HardwareManager(DummyDB(),None)
    _, rec=hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'),'verify')
    assert rec['verified'] is False
    assert 'verify' not in mgr.status()['actual']


def test_warmup_records_actual_and_disables_cpu_fallback(monkeypatch, tmp_path):
    import sys, types
    import metatron.hardware as hw
    seen={}
    class T:
        def __init__(self,name): self.name=name
    class H:
        def __init__(self): self.type=T('NPU'); self.name='NPU-A'
    class D:
        hardware_device=H(); ep_name='FutureNpuEP'
    class SO:
        def __init__(self): self.cfg={}; self.dev=None
        def add_session_config_entry(self,k,v): self.cfg[k]=v
        def add_provider_for_devices(self,ds,opts): self.dev=ds[0]
    def make(path,sess_options=None,**kw): seen.update(sess_options.cfg); return object()
    fake=types.SimpleNamespace(get_ep_devices=lambda:[D()],SessionOptions=SO,InferenceSession=make,get_available_providers=lambda:[])
    monkeypatch.setitem(sys.modules,'onnxruntime',fake)
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[]); monkeypatch.setattr(hw,'_windows_accelerators',lambda:[])
    mgr=HardwareManager(DummyDB(),None)
    _, rec=hw.WindowsMLSessionFactory(mgr).create_session(str(tmp_path/'m.onnx'),'verify',warmup=lambda s:None,require_verified=True)
    assert seen['session.disable_cpu_ep_fallback']=='1'
    assert rec['verified'] is True and mgr.status()['actual']['verify']['kind']=='NPU'


def test_configured_windows_ml_devices_are_merged_as_routable(monkeypatch, tmp_path):
    import metatron.hardware as hw
    fake_py=tmp_path/'python.exe'; fake_py.write_text('x')
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[]); monkeypatch.setattr(hw,'_windows_accelerators',lambda:[])
    def worker(self, command, names=None, timeout=180.0):
        assert command=='devices'
        return {'configured':True,'registration_scope':'current_process','devices':[{'kind':'NPU','ep_name':'QNNExecutionProvider','name':'Snapdragon NPU','vendor':'Qualcomm','device_id':'n0'},{'kind':'GPU','ep_name':'DmlExecutionProvider','name':'GPU','vendor':'Test','device_id':'g0'}]}
    monkeypatch.setattr(HardwareManager,'_winml_worker',worker)
    mgr=HardwareManager(DummyDB(),None,winml_python=str(fake_py))
    candidates=mgr.candidates('stt')
    assert [x['kind'] for x in candidates[:3]]==['NPU','GPU','CPU']
    assert candidates[0]['provider']=='QNNExecutionProvider'
    assert candidates[0]['routable'] is True
