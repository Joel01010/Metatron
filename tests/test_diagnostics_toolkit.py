import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def module(name):
    path=ROOT/'scripts'/'diagnostics'/(name+'.py')
    spec=importlib.util.spec_from_file_location('diag_'+name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class TestDiagnostics(unittest.TestCase):
    def test_summary_no_samples_is_incomplete(self):
        d=module('analyze_telemetry').summarize([],{})
        self.assertEqual(d['status'],'INCOMPLETE')
        self.assertIsNone(d['metrics']['resident_mib']['p95'])

    def test_windows_null_gpu_not_zero(self):
        x={'ts':1000,'process_count':1,'working_set_mib':100,'private_working_set_mib':90,'private_bytes_mib':120,'gpu_3d_percent':None,'system_committed_mib':3000}
        y=dict(x,ts=2000,working_set_mib=110)
        d=module('analyze_telemetry').summarize([x,y],{'root_pid':123,'samples':[x,y],'gpu_counter_error':'no driver'})
        self.assertFalse(d['metrics']['gpu_3d_percent']['available'])
        self.assertIn('gpu_3d_percent',d['missing_metrics'])
        self.assertEqual(d['metrics']['private_commit_mib']['peak'],120)
        self.assertEqual(d['status'],'CAPTURED_NOT_CERTIFIED')

    def test_linux_uss_is_not_private_commit(self):
        x={'ts':1000,'process_count':1,'rss_mib':120,'private_mib':80,'cpu_seconds':1}
        y=dict(x,ts=2000,cpu_seconds=1.25)
        d=module('analyze_telemetry').summarize([x,y],{})
        self.assertEqual(d['metrics']['private_uss_mib']['median'],80)
        self.assertIsNone(d['metrics']['private_commit_mib']['p95'])
        self.assertGreater(d['metrics']['cpu_percent']['median'],0)

    def test_pid_exit_marked_incomplete(self):
        x={'ts':1000,'root_error':'root_exited'}
        y={'ts':2000,'root_error':None}
        self.assertEqual(module('analyze_telemetry').summarize([x,y],{})['status'],'INCOMPLETE')

    def test_pct(self):
        a=module('analyze_telemetry')
        self.assertEqual(a.percentile([0,10],.95),9.5)
        self.assertIsNone(a.percentile([None,float('nan')],.95))

    def test_baseline_comparison_and_jsonl(self):
        m=module('analyze_telemetry')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'log.jsonl'
            p.write_text('\n'.join(json.dumps(o) for o in [{'meta':{'schema':1}}, {'sample':{'ts':10,'rss_mib':20}}, {'sample':{'ts':20,'rss_mib':30}}]))
            samples,meta=m.load(p)
            self.assertEqual(len(samples),2)
            a=m.summarize(samples,meta)
            self.assertEqual(m.compare(a,a)['resident_mib']['delta'],0)

    def test_run_suite_sanitized_bundle(self):
        runner=module('run_diagnostics')
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)
            (directory/'environment.json').write_text('{}')
            (directory/'manifest-test.txt').write_text('ok')
            target=directory/'bundle.zip'
            runner.bundle(directory,target)
            import zipfile
            with zipfile.ZipFile(target) as z:
                self.assertIn('manifest.json',z.namelist())
                self.assertNotIn(target.name,z.namelist())

    def test_runner_summary_does_not_expose_command_arguments(self):
        runner=module('run_diagnostics')
        with tempfile.TemporaryDirectory() as d:
            secret='C:/Users/privateuser/hidden-project'
            result=runner.run_step('probe',[sys.executable,'-c','print(1)',secret],Path(d),Path(d),timeout=10)
            self.assertEqual(result['status'],'PASS')
            self.assertNotIn(secret,json.dumps(result))

    def test_windows_collector_requires_complete_memory_coverage(self):
        script=(ROOT/'scripts/Collect-WindowsMetrics.ps1').read_text(encoding='utf-8')
        self.assertIn('$privateWorkingCount -eq $ids.Count',script)
        self.assertIn('$readCount -eq $ids.Count',script)
        self.assertIn('private_working_set_mib=$(if(',script)

    def test_sampler_invalid_pid_rejected(self):
        cmd=[sys.executable,str(ROOT/'scripts/diagnostics/process_sampler.py'),'--pid','-2','--seconds','2','--out',os.devnull]
        cp=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
        self.assertNotEqual(cp.returncode,0)

if __name__=='__main__':unittest.main()
