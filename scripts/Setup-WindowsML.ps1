param(
  [string]$Root = "",
  [string]$Python = "python"
)
$ErrorActionPreference = 'Stop'
function Invoke-NativeChecked {
  param([Parameter(Mandatory=$true)][string]$FilePath,[string[]]$ArgumentList=@(),[string]$Label='native command')
  $old=$ErrorActionPreference;$code=1
  try{$ErrorActionPreference='Continue';& $FilePath @ArgumentList;$code=$LASTEXITCODE}finally{$ErrorActionPreference=$old}
  if($null-eq$code){$code=0}
  if($code-ne0){throw "$Label failed with exit $code"}
}
if (-not $Root) {
  $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData\Local' }
  $Root = Join-Path $base 'Metatron\runtimes\winml'
}
$Root = [IO.Path]::GetFullPath($Root)
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$Venv = Join-Path $Root '.venv'
$Py = Join-Path $Venv 'Scripts\python.exe'
if (-not (Test-Path $Py)) {
  Invoke-NativeChecked -FilePath $Python -ArgumentList @('-m','venv',$Venv) -Label 'Windows ML venv creation'
}
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','--upgrade','pip') -Label 'Windows ML pip upgrade'
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','wasdk-Microsoft.Windows.AI.MachineLearning[all]','wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap','onnxruntime-windowsml','numpy') -Label 'Windows ML dependency install'
$env:METATRON_WINML_PYTHON=$Py
[Environment]::SetEnvironmentVariable('METATRON_WINML_PYTHON', $Py, 'User')
Write-Host "Windows ML runtime ready: $Py" -ForegroundColor Green
Write-Host 'METATRON_WINML_PYTHON is active now and persisted for future user sessions.'
