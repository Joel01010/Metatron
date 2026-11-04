from pathlib import Path
import os, subprocess, json, sys
py=os.environ.get('METATRON_WINML_PYTHON','')
if not py or not Path(py).is_file():
    raise SystemExit('METATRON_WINML_PYTHON is not configured. Run Setup-WindowsML.ps1 first.')
worker=Path(__file__).with_name('winml_worker.py')
p=subprocess.run([py,str(worker),'--once','catalog'],text=True,capture_output=True)
print(p.stdout)
if p.returncode: print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
