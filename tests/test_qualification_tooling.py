import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(tmp,pws):
 rows=[{'ts':i*1000,'private_working_set_mib':pws,'working_set_mib':pws+20,'private_bytes_mib':pws+50,'process_cpu_seconds':i*.02,'logical_processors':16,'gpu_3d_percent':1.0} for i in range(6)];m=tmp/'m.json';m.write_text(json.dumps({'schema':2,'interval_ms':1000,'samples':rows}));o=tmp/'o.json';cp=subprocess.run([sys.executable,str(ROOT/'scripts/Analyze-WindowsQualification.py'),str(m),'--scenario','idle_shell','--json-out',str(o)],capture_output=True,text=True);return cp,json.loads(o.read_text())
def test_qualification(tmp_path):
 cp,r=run(tmp_path,300);assert cp.returncode==0 and r['overall']=='PASS';cp,r=run(tmp_path,700);assert cp.returncode==2 and r['overall']=='FAIL'
def test_thresholds():
 t=json.loads((ROOT/'qualification_thresholds.json').read_text())['gates'];assert t['strict_logical_managed_ceiling_mib']==2816 and t['bridge_p95_ms']==15
