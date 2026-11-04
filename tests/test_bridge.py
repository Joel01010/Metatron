from __future__ import annotations
import time
from types import SimpleNamespace

from metatron.db import Database
from metatron.events import EventBus
from metatron.main import StdoutBridge


def test_push_bridge_coalesces_levels_and_keeps_control_order(tmp_path):
    db=Database(tmp_path/'b.db'); bus=EventBus(db); app=SimpleNamespace(bus=bus)
    bridge=StdoutBridge(app)
    captured=[]
    bridge.write=lambda obj: captured.append(obj)  # type: ignore[method-assign]
    try:
        bridge.set_live(True,'orb')
        bus.emit('system.one','test',{'n':1})
        for i in range(20): bus.emit_ephemeral('speech.user.level','test',{'level':i/20})
        bus.emit('system.two','test',{'n':2})
        deadline=time.time()+0.5
        while time.time()<deadline and len(captured)<3: time.sleep(.01)
        topics=[x['params']['topic'] for x in captured if x.get('method')=='metatron.event']
        assert topics.index('system.one') < topics.index('system.two')
        levels=[x for x in captured if x.get('method')=='metatron.event' and x['params']['topic']=='speech.user.level']
        assert 1 <= len(levels) < 20
        assert levels[-1]['params']['payload']['level'] == 19/20
    finally:
        bridge.close(); db.close()


def test_no_high_rate_push_when_no_visible_consumer(tmp_path):
    db=Database(tmp_path/'b.db'); bus=EventBus(db); app=SimpleNamespace(bus=bus)
    bridge=StdoutBridge(app); captured=[]; bridge.write=lambda obj: captured.append(obj)  # type: ignore[method-assign]
    try:
        for i in range(10): bus.emit_ephemeral('speech.user.level','test',{'level':.5})
        time.sleep(.08)
        assert not [x for x in captured if x.get('method')=='metatron.event' and x['params']['topic']=='speech.user.level']
    finally:
        bridge.close(); db.close()
