import time
from pathlib import Path
import pytest
from metatron.config import AppConfig
from metatron.core import Metatron
from metatron.schema import SchemaError,validate_protocol_request
from metatron.server import Dispatcher,ProtocolError

def test_protocol_validation():
 with pytest.raises(SchemaError):validate_protocol_request([])
 with pytest.raises(SchemaError):validate_protocol_request({'id':1,'cmd':'','params':{}})
 with pytest.raises(SchemaError):validate_protocol_request({'id':1,'cmd':'status','params':[]})
 assert validate_protocol_request({'id':'a','cmd':' status ','params':{}})==('a','status',{})
def test_dispatch_params(tmp_path:Path):
 a=Metatron(AppConfig(data_dir=tmp_path,enable_background_maintenance=False,tts_enabled=False))
 try:
  with pytest.raises(ProtocolError):Dispatcher(a).dispatch('status',[]) # type: ignore
 finally:a.close()
def test_history_prune(tmp_path:Path):
 a=Metatron(AppConfig(data_dir=tmp_path,enable_background_maintenance=False,tts_enabled=False))
 try:
  a.settings.set('dictation',{'history_days':1,'history_max_items':100});old=a.history.record('old');pin=a.history.record('pinned');a.history.set_pinned(pin['id'],True);ts=time.time()-5*86400;a.db.execute('UPDATE dictation_history SET created_at=? WHERE id IN (?,?)',(ts,old['id'],pin['id']));r=a.maintenance_tick();assert r['pruned_history']==1;assert [x['text'] for x in a.history.list()]==['pinned']
 finally:a.close()

def test_invalid_request_response_keeps_request_id(tmp_path):
    import json, os, subprocess, sys
    env=os.environ.copy();env['METATRON_DATA_DIR']=str(tmp_path);env['PYTHONPATH']=str(Path(__file__).resolve().parents[1])
    p=subprocess.Popen([sys.executable,'-X','utf8','-m','metatron.main'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        p.stdin.write(json.dumps({'id':77,'cmd':'status','params':[]})+'\n');p.stdin.flush()
        out=json.loads(p.stdout.readline())
        assert out['id']==77 and out['ok'] is False and out['error']['code']=='invalid_request'
    finally:
        p.stdin.close();p.wait(timeout=5);p.stdout.close();p.stderr.close()
