param([string]$Root="",[string]$Python="python")
$ErrorActionPreference='Stop'
function Invoke-NativeChecked {
  param([Parameter(Mandatory=$true)][string]$FilePath,[string[]]$ArgumentList=@(),[string]$Label='native command')
  $oldEap=$ErrorActionPreference; $code=1
  try{$ErrorActionPreference='Continue'; & $FilePath @ArgumentList; $code=$LASTEXITCODE}finally{$ErrorActionPreference=$oldEap}
  if($code-ne0){throw "$Label failed with exit $code"}
}
if(-not$Root){$base=if($env:LOCALAPPDATA){$env:LOCALAPPDATA}else{Join-Path $HOME 'AppData\Local'};$Root=Join-Path $base 'Metatron\runtimes\qualification'}
$Venv=Join-Path $Root '.venv'
New-Item -ItemType Directory -Force $Root|Out-Null
if(-not(Test-Path(Join-Path $Venv 'Scripts\python.exe'))){Invoke-NativeChecked -FilePath $Python -ArgumentList @('-m','venv',$Venv) -Label 'qualification venv creation'}
$Py=Join-Path $Venv 'Scripts\python.exe'
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','--upgrade','pip') -Label 'qualification pip upgrade'
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','openvino','sounddevice','numpy') -Label 'qualification dependency install'
$env:METATRON_QUALIFICATION_PYTHON=$Py
[Environment]::SetEnvironmentVariable('METATRON_QUALIFICATION_PYTHON',$Py,'User')
Write-Host "Qualification runtime ready: $Py"
