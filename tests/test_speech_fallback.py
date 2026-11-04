from __future__ import annotations
from types import SimpleNamespace

from metatron.hardware import Accelerator, HardwareManager
from metatron.memory import ModelBroker, Reservation
from metatron.speech import SpeechRuntime

class DB:
    def get_setting(self,k,d=None): return d
    def set_setting(self,k,v): pass
class Bus:
    def __init__(self): self.events=[]
    def emit(self,*a,**k): self.events.append((a,k))
    def emit_ephemeral(self,*a,**k): self.events.append((a,k))
class Presence:
    def __getattr__(self,n): return lambda *a,**k: None


def test_speech_runtime_tries_npu_then_gpu(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[])
    monkeypatch.setattr(hw,'_windows_accelerators',lambda:[Accelerator('n','NPU','NPU',provider='x'),Accelerator('g','GPU','GPU',provider='y')])
    hardware=HardwareManager(DB(),None)
    broker=ModelBroker(3000); broker.register(Reservation('parakeet-unified-en-0.6b',1000)); broker.load('parakeet-unified-en-0.6b')
    runtime=SpeechRuntime([],broker,hardware,Bus(),Presence())
    calls=[]
    def request(cmd,params=None,timeout_s=30):
        if cmd=='list_ov_devices': return {'devices':['NPU','GPU','CPU']}
        if cmd=='set_config':
            calls.append(params['device'])
            if params['device']=='NPU': raise RuntimeError('compile failed')
            if params['device']=='GPU': return {'placement_verified':True,'actual_device':'GPU','provider':'OpenVINO','device_name':'GPU.0'}
            raise AssertionError('CPU should not be reached')
        raise AssertionError(cmd)
    monkeypatch.setattr(SpeechRuntime, 'request', lambda self, cmd, params=None, timeout_s=30: request(cmd, params, timeout_s))
    runtime._configure_best_device(); runtime._apply_config()
    assert calls==['NPU','GPU']
    assert runtime.status()['actual_device']['kind']=='GPU'


def test_speech_runtime_rejects_silent_class_mismatch(monkeypatch):
    import metatron.hardware as hw
    monkeypatch.setattr(hw,'_openvino_devices',lambda:[]); monkeypatch.setattr(hw,'_onnxruntime_providers',lambda:[]); monkeypatch.setattr(hw,'_windows_accelerators',lambda:[])
    hardware=HardwareManager(DB(),None)
    broker=ModelBroker(3000); broker.register(Reservation('parakeet-unified-en-0.6b',1000)); broker.load('parakeet-unified-en-0.6b')
    runtime=SpeechRuntime([],broker,hardware,Bus(),Presence())
    calls=[]
    def request(cmd,params=None,timeout_s=30):
        if cmd=='list_ov_devices': return {'devices':['NPU','GPU']}
        if cmd=='set_config':
            calls.append(params['device'])
            if params['device']=='NPU': return {'placement_verified':True,'actual_device':'CPU'}
            return {'placement_verified':True,'actual_device':'GPU'}
    monkeypatch.setattr(SpeechRuntime, 'request', lambda self, cmd, params=None, timeout_s=30: request(cmd, params, timeout_s))
    runtime._configure_best_device(); runtime._apply_config()
    assert calls==['NPU','GPU']
    assert runtime.status()['actual_device']['kind']=='GPU'


def test_injection_blocked_is_explicit_event(tmp_path):
    from metatron.events import EventBus
    from metatron.presence import PresenceController
    from metatron.hardware import HardwareManager
    from metatron.memory import ModelBroker
    from metatron.config import MEMORY_PROFILES
    from metatron.speech import SpeechRuntime, SpeechSettings
    from metatron.db import Database
    db=Database(tmp_path/'events.sqlite3')
    bus=EventBus(db)
    seen=[]; bus.subscribe(lambda ev: seen.append(ev))
    rt=SpeechRuntime(command=[], broker=ModelBroker(MEMORY_PROFILES['strict'].hard_limit_mib), hardware=HardwareManager(), bus=bus, presence=PresenceController(bus), settings=SpeechSettings())
    rt._handle_event({'event':'state','state':'INJECTION_BLOCKED','detail':'elevated target','transcript':'hello'})
    payloads=[e.payload for e in seen if e.topic=='speech.injection.blocked']
    assert payloads and payloads[-1]['transcript']=='hello'
    assert payloads[-1]['method']=='paste'
    db.close()
