from pathlib import Path
from metatron.config import AppConfig
from metatron.core import Metatron
from metatron.server import Dispatcher
def test_protocol_info(tmp_path:Path):
 a=Metatron(AppConfig(data_dir=tmp_path,enable_background_maintenance=False,tts_enabled=False))
 try:
  i=Dispatcher(a).dispatch('protocol.info',{});assert i['protocol_version']>=2;assert 'dictation' in i['certified_core'];assert 'agents' in i['experimental']
 finally:a.close()
