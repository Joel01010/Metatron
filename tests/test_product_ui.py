import json,re
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class P(HTMLParser):
 def __init__(self):super().__init__();self.ids=[]
 def handle_starttag(self,t,a):self.ids += [v for k,v in a if k=='id' and v]
def test_ui_contract():
 h=(ROOT/'ui/index.html').read_text();p=P();p.feed(h);assert len(p.ids)==len(set(p.ids));
 for v in ('command','dictation','history','vocabulary','hardware','models','voice','metrics','tasks','agents','diagnostics','settings'):assert f'id="view-{v}"' in h
 assert 'id="commandPalette"' in h and 'id="onboarding"' in h
def test_security_files():
 c=json.loads((ROOT/'src-tauri/tauri.conf.json').read_text());assert c['app']['security']['csp'] and 'unsafe-eval' not in c['app']['security']['csp'].lower();assert len(list(ROOT.rglob('orb-renderer.js')))==1
