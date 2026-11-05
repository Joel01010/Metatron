#!/usr/bin/env python3
from __future__ import annotations
import json,os,platform,tempfile,threading,time,wave
from pathlib import Path

def main():
 if platform.system()!='Windows': print(json.dumps({'schema':1,'version':'1.4.0','status':'SKIP','reason':'Windows-only'}));return 3
 try:
  import winsound
  from metatron.memory import ModelBroker,Reservation
  from metatron.tts import WindowsSapiProvider
 except Exception as e: print(json.dumps({'schema':1,'version':'1.4.0','status':'FAIL','error':str(e)}));return 2
 broker=ModelBroker(256);broker.register(Reservation('windows-sapi-tts',64))
 p=WindowsSapiProvider(broker)
 if not p.available(): print(json.dumps({'schema':1,'version':'1.4.0','status':'SKIP','reason':'Windows SAPI unavailable'}));return 3
 with tempfile.TemporaryDirectory() as td:
  wav=Path(td)/'interrupt.wav';p.synthesize('This is a deliberately long Metatron speech interruption verification sentence. '*8,wav,'',1.0)
  dur=0.0
  with wave.open(str(wav),'rb') as w: dur=w.getnframes()/w.getframerate()
  done=threading.Event()
  def play():
   try:winsound.PlaySound(str(wav),winsound.SND_FILENAME)
   finally:done.set()
  t=threading.Thread(target=play,daemon=True);t.start();time.sleep(0.3);t0=time.perf_counter();winsound.PlaySound(None,0);ok=done.wait(1.0);stop_ms=(time.perf_counter()-t0)*1000
  out={'schema':1,'version':'1.4.0','status':'PASS' if ok and dur>1 else 'FAIL','wav_duration_s':round(dur,3),'stop_latency_ms':round(stop_ms,2)};print(json.dumps(out,indent=2));return 0 if out['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
