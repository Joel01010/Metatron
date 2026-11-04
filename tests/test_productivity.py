from pathlib import Path
from metatron.db import CURRENT_SCHEMA_VERSION,Database
from metatron.events import EventBus
from metatron.productivity import AppRuleStore,DictationHistory,VocabularyStore

def test_schema_v2(tmp_path:Path):
 d=Database(tmp_path/'m.db');
 try:
  assert d.schema_version==CURRENT_SCHEMA_VERSION>=2;names={r['name'] for r in d.query("SELECT name FROM sqlite_master WHERE type='table'")};assert {'dictation_history','vocabulary','app_rules'}<=names
 finally:d.close()
def test_history(tmp_path:Path):
 d=Database(tmp_path/'m.db');h=DictationHistory(d,EventBus(d))
 try:
  a=h.record('Hello Metatron',app_id='code.exe',context_profile='code',device_kind='NPU');b=h.record('failed',status='failed',error='boom');assert h.stats()['total']==2;assert h.list(query='Metatron')[0]['id']==a['id'];h.set_pinned(a['id'],True);assert h.list(pinned_only=True)[0]['pinned'];assert h.delete(b['id']);assert h.clear(keep_pinned=True)==0
 finally:d.close()
def test_vocab(tmp_path:Path):
 d=Database(tmp_path/'m.db');v=VocabularyStore(d)
 try:
  a=v.upsert('Supabase');b=v.upsert('supabase',replacement='Supabase');assert a['id']==b['id'];assert v.observe_text('Deploy to Supabase')==1;assert v.list()[0]['usage_count']==1
 finally:d.close()
def test_rules(tmp_path:Path):
 d=Database(tmp_path/'m.db');r=AppRuleStore(d)
 try:
  assert r.evaluate('x.exe')['privacy_action']=='allow';r.upsert('bank.exe',privacy_action='pause',context_profile='personal');assert r.evaluate('BANK.EXE')['privacy_action']=='pause'
 finally:d.close()
