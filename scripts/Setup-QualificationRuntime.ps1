param([string]$Root="",[string]$Python="python")
$ErrorActionPreference='Stop';if(-not$Root){$base=if($env:LOCALAPPDATA){$env:LOCALAPPDATA}else{Join-Path $HOME 'AppData\Local'};$Root=Join-Path $base 'Metatron\runtimes\qualification'}
$Venv=Join-Path $Root '.venv';New-Item -ItemType Directory -Force $Root|Out-Null;if(-not(Test-Path(Join-Path $Venv 'Scripts\python.exe'))){& $Python -m venv $Venv};$Py=Join-Path $Venv 'Scripts\python.exe';& $Py -m pip install --upgrade pip;& $Py -m pip install openvino sounddevice numpy
[Environment]::SetEnvironmentVariable('METATRON_QUALIFICATION_PYTHON',$Py,'User');Write-Host "Qualification runtime ready: $Py"
