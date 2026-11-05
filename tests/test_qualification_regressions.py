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


def test_windows_reverification_regressions_are_locked_down():
    pyproject=(ROOT/'pyproject.toml').read_text(encoding='utf-8')
    assert '--basetemp=.pytest-tmp' in pyproject
    assert 'tmp_path_retention_policy = "failed"' in pyproject

    desktop=(ROOT/'scripts/Measure-MetatronDesktop.ps1').read_text(encoding='utf-8')
    assert desktop.count('{') == desktop.count('}')

    wrapper=(ROOT/'scripts/Invoke-MetatronV14Qualification.ps1').read_text(encoding='utf-8')
    assert '$fwd=@(' in wrapper
    assert '@fwd' in wrapper
    assert '$args=@(' not in wrapper
    assert 'Test-Path $qroot' in wrapper
    assert '$qroot -and' in wrapper

    full=(ROOT/'scripts/Invoke-MetatronFullValidation.ps1').read_text(encoding='utf-8')
    assert 'if($SoakMinutes -gt 0)' in full
    assert 'if($SoakMinutes -gt 0 -and $overall)' not in full
    assert 'RequireSpeechRuntime' in full


def test_tts_interrupt_contract_uses_async_windows_playback():
    test_script=(ROOT/'scripts/Test-WindowsTTSInterrupt.py').read_text(encoding='utf-8')
    tts=(ROOT/'metatron/tts.py').read_text(encoding='utf-8')
    assert 'SND_ASYNC' in test_script
    assert 'MAX_STOP_LATENCY_MS = 2000.0' in test_script
    assert 'interrupted_before_natural_end' in test_script
    assert 'SND_ASYNC' in tts
    assert 'PlaySound(None, 0)' in tts


def test_memory_collector_records_leak_diagnostics():
    collector=(ROOT/'scripts/Collect-WindowsMetrics.ps1').read_text(encoding='utf-8')
    for token in ('handle_count','thread_count','process_details','process_added_pids',
                  'process_removed_pids','sample_elapsed_ms','interval_overrun_ms',
                  'system_commit_percent','GpuPollIntervalSeconds'):
        assert token in collector
    soak=(ROOT/'scripts/Analyze-Soak.py').read_text(encoding='utf-8')
    assert 'max-quartile-delta-mib' in soak
    assert 'min-complete-ratio' in soak
    assert 'handle_count_quartile_delta' in soak
    assert 'private_bytes_slope_mib_per_hour' in soak
    assert 'private_bytes_complete_ratio' in soak


def test_product_audit_accepts_rustfmt_allowlist():
    audit = (ROOT / "scripts" / "product_audit.py").read_text(encoding="utf-8")
    rust = (ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    assert "matches!(\n        cmd," in rust
    assert r"main_allowed\s*" in audit
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "product_audit.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
