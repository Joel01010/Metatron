"""Regression checks for portable release and Windows qualification contracts."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def _qualify(tmp_path, samples, scenario='idle_shell'):
    metrics=tmp_path/'metrics.json'; result=tmp_path/'qualification.json'
    metrics.write_text(json.dumps({'schema':3,'samples':samples}),encoding='utf-8')
    proc=subprocess.run([sys.executable,str(ROOT/'scripts/Analyze-WindowsQualification.py'),str(metrics),
                         '--scenario',scenario,'--json-out',str(result)],capture_output=True,text=True)
    return proc,json.loads(result.read_text(encoding='utf-8'))

def test_empty_metrics_cannot_certify(tmp_path):
    proc,result=_qualify(tmp_path,[])
    assert proc.returncode != 0
    assert result['overall']=='FAIL'

def test_missing_private_working_set_cannot_certify(tmp_path):
    rows=[{'ts':i*1000,'process_cpu_seconds':i*.01,'logical_processors':8} for i in range(5)]
    proc,result=_qualify(tmp_path,rows)
    assert proc.returncode != 0
    assert any(g['status']=='FAIL' and 'private working set' in g['name'] for g in result['gates'])

def test_missing_gpu_counter_not_assumed_zero(tmp_path):
    rows=[{'ts':i*1000,'private_working_set_mib':250,'process_cpu_seconds':i*.01,'logical_processors':8,
           'gpu_3d_percent':None} for i in range(5)]
    proc,result=_qualify(tmp_path,rows,'orb_balanced')
    assert result['overall']=='WARN' and result['metrics']['gpu_3d_percent']['median'] is None

def test_windows_script_contracts():
    metrics=(ROOT/'scripts/Collect-WindowsMetrics.ps1').read_text(encoding='utf-8')
    assert 'RootProcessId' in metrics and 'Get-BoundedGpuCounters' in metrics
    assert 'Wait-Job -Job $job -Timeout' in metrics and '[switch]$SkipGpu' in metrics
    validate=(ROOT/'scripts/Invoke-MetatronFullValidation.ps1').read_text(encoding='utf-8')
    assert 'function Run($n,$exe,$argList' in validate and '& $exe @argList' in validate
    tauri=(ROOT/'src-tauri/Cargo.toml').read_text(encoding='utf-8')
    assert 'version = "1.4.0"' in tauri
    assert (ROOT/'src-tauri/icons/icon.ico').is_file()
    assert (ROOT/'src-tauri/resources/.gitkeep').is_file()

def test_core_without_commit_baseline_is_not_certified(tmp_path):
    rows=[{'ts':i*1000,'private_working_set_mib':200,'process_cpu_seconds':i*.01,'logical_processors':8}
          for i in range(5)]
    proc,result=_qualify(tmp_path,rows,'certified_core')
    assert proc.returncode != 0
    assert any(g['name']=='certified-core system commit delta' and g['status']=='FAIL'
               for g in result['gates'])

def test_opencode_status_probe_is_cached(monkeypatch):
    from metatron.agents.opencode import OpenCodeAdapter
    a=OpenCodeAdapter()
    calls=[]
    def fake():
        calls.append(1)
        return False
    monkeypatch.setattr(OpenCodeAdapter,'server_available',lambda self:fake())
    a.status();a.status()
    assert len(calls)==1
