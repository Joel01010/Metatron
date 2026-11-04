param(
  [string]$Root = "",
  [string]$Python = "python"
)
$ErrorActionPreference = 'Stop'
if (-not $Root) {
  $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME 'AppData\Local' }
  $Root = Join-Path $base 'Metatron\runtimes\winml'
}
$Root = [IO.Path]::GetFullPath($Root)
New-Item -ItemType Directory -Force -Path $Root | Out-Null
$Venv = Join-Path $Root '.venv'
if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
  & $Python -m venv $Venv
}
$Py = Join-Path $Venv 'Scripts\python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install "wasdk-Microsoft.Windows.AI.MachineLearning[all]" wasdk-Microsoft.Windows.ApplicationModel.DynamicDependency.Bootstrap onnxruntime-windowsml
[Environment]::SetEnvironmentVariable('METATRON_WINML_PYTHON', $Py, 'User')
Write-Host "Windows ML runtime ready: $Py"
Write-Host "Restart Metatron, then open Hardware and press Re-scan / Ensure Windows ML EPs."
