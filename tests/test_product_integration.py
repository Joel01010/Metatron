from pathlib import Path
from metatron.config import AppConfig
from metatron.core import Metatron

def app(tmp):return Metatron(AppConfig(data_dir=tmp,enable_background_maintenance=False,tts_enabled=False))
def test_transcript_opt_in(tmp_path:Path):
 a=app(tmp_path)
 try:
  a.bus.emit('speech.transcript.final','speech',{'text':'not saved'});assert a.history.stats()['total']==0;a.settings.set('privacy',{'save_transcripts':True});a.bus.emit('speech.transcript.final','speech',{'text':'saved','app_id':'code.exe','context_profile':'code'});assert a.history.list()[0]['text']=='saved'
 finally:a.close()
def test_diagnostics(tmp_path:Path):
 a=app(tmp_path)
 try:
  r=a.diagnostics.summary();keys={x['key'] for x in r['checks']};assert {'database_schema','accelerator_route','speech_runtime'}<=keys;assert isinstance(r['ready_for_core_use'],bool)
 finally:a.close()
def test_active_app_policy_visible(tmp_path:Path):
 a=app(tmp_path)
 try:
  a.app_rules.upsert('bank.exe',privacy_action='pause',context_profile='personal');a.speech._privacy_runtime_supported=False;a.speech._handle_event({'event':'active_app','app_id':'BANK.EXE','app_name':'Bank'});st=a.speech.status();assert st['active_app']['paused_by_policy'];assert st['privacy_runtime_supported'] is False
 finally:a.close()

def test_privacy_paused_transcript_never_enters_history_or_vocabulary(tmp_path:Path):
 a=app(tmp_path)
 try:
  a.settings.set('privacy',{'save_transcripts':True})
  before=a.vocabulary.list()
  a.bus.emit('speech.transcript.final','speech',{
   'text':'private supabase note','raw_text':'private supabase note',
   'status':'privacy_paused','app_id':'bank.exe','context_profile':'personal'})
  assert a.history.stats()['total']==0
  assert a.vocabulary.list()==before
 finally:a.close()
