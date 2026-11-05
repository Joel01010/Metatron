from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_v14_versions_are_aligned():
 assert 'version = "1.4.0"' in (ROOT/'pyproject.toml').read_text(encoding='utf-8')
 assert 'version = "1.4.0"' in (ROOT/'src-tauri/Cargo.toml').read_text(encoding='utf-8')
 assert '"version": "1.4.0"' in (ROOT/'src-tauri/tauri.conf.json').read_text(encoding='utf-8')
 assert '__version__ = "1.4.0"' in (ROOT/'metatron/__init__.py').read_text(encoding='utf-8')
 assert json.loads((ROOT/'qualification_thresholds.json').read_text())['version']=='1.4.0'

def test_v14_qualification_scripts_present():
 names=['Verify-OpenVINODevices.py','Test-WindowsAudio.py','Test-WindowsTTSInterrupt.py','Analyze-Soak.py','Measure-MetatronSoak.ps1','Verify-WindowsArtifacts.ps1','Test-PowerShellScripts.ps1','Test-OrbWindow.ps1','Setup-QualificationRuntime.ps1','Invoke-EZSTTQualification.ps1']
 for n in names: assert (ROOT/'scripts'/n).is_file(), n

def test_soak_analyzer_passes_flat_and_fails_growth(tmp_path):
 def run(vals,gate):
  start=1000000; p=tmp_path/'m.json';o=tmp_path/'o.json';p.write_text(json.dumps({'samples':[{'ts':start+i*900000,'private_working_set_mib':v} for i,v in enumerate(vals)]}))
  cp=subprocess.run([sys.executable,str(ROOT/'scripts/Analyze-Soak.py'),str(p),'--max-growth-mib-per-hour',str(gate),'--json-out',str(o)],capture_output=True,text=True)
  return cp.returncode,json.loads(o.read_text())
 rc,out=run([300,301,300,302,301,302],64);assert rc==0 and out['status']=='PASS'
 rc,out=run([300,350,400,450,500,550],64);assert rc==2 and out['status']=='FAIL'

def test_rust_orb_reposition_is_wired():
 s=(ROOT/'src-tauri/src/main.rs').read_text(encoding='utf-8')
 assert 'position_orb_on_primary' in s
 assert 'primary_monitor()' in s
 assert 'set_position(PhysicalPosition::new' in s
 assert '"orb.reposition"' in s

def test_windows_ci_builds_full_package():
 s=(ROOT/'.github/workflows/ci.yml').read_text(encoding='utf-8')
 assert 'Full Windows package build' in s
 assert 'Verify-WindowsArtifacts.ps1' in s
 assert 'Test-PowerShellScripts.ps1' in s
