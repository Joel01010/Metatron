param(
  [string]$Python = "python",
  [string]$BuildVenv = ""
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $BuildVenv) { $BuildVenv = Join-Path $env:LOCALAPPDATA 'Metatron\build-venv' }
Set-Location $Root

function Invoke-NativeChecked {
  param([Parameter(Mandatory=$true)][string]$FilePath,[string[]]$ArgumentList=@(),[string]$Label='native command')
  $old=$ErrorActionPreference;$code=1
  try{$ErrorActionPreference='Continue';& $FilePath @ArgumentList;$code=$LASTEXITCODE}finally{$ErrorActionPreference=$old}
  if($null-eq$code){$code=0}
  if($code-ne0){throw "$Label failed with exit $code"}
}

$Py = Join-Path $BuildVenv 'Scripts\python.exe'
if (-not (Test-Path $Py)) {
  Invoke-NativeChecked -FilePath $Python -ArgumentList @('-m','venv',$BuildVenv) -Label 'build venv creation'
}
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','--upgrade','pip','setuptools','wheel') -Label 'build pip upgrade'
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','pyinstaller','-e','.[dev]') -Label 'build dependencies'

$oldPlugin=$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD;$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
try { Invoke-NativeChecked -FilePath $Py -ArgumentList @('-W','error','-m','pytest','tests','-q') -Label 'Python tests' }
finally { $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=$oldPlugin }
Invoke-NativeChecked -FilePath $Py -ArgumentList @('scripts\product_audit.py') -Label 'product audit'

$Dist = Join-Path $Root 'build\backend'
$Work = Join-Path $Root 'build\pyinstaller'
Remove-Item $Dist,$Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$sep = ';'
$pyInstallerArgs=@(
  '-m','PyInstaller','--noconfirm','--clean','--onedir','--name','metatron-backend',
  '--paths',$Root,
  '--add-data',((Join-Path $Root 'scripts\kokoro_onnx_worker.py')+$sep+'scripts'),
  '--add-data',((Join-Path $Root 'scripts\winml_worker.py')+$sep+'scripts'),
  '--distpath',$Dist,'--workpath',$Work,'--specpath',$Work,
  (Join-Path $Root 'scripts\backend_entry.py')
)
Invoke-NativeChecked -FilePath $Py -ArgumentList $pyInstallerArgs -Label 'backend packaging'

$Resources = Join-Path $Root 'src-tauri\resources'
New-Item -ItemType Directory -Force -Path $Resources | Out-Null
Remove-Item (Join-Path $Resources 'metatron-backend') -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Dist 'metatron-backend') (Join-Path $Resources 'metatron-backend') -Recurse -Force

$cargo=Get-Command cargo -ErrorAction SilentlyContinue
if (-not $cargo) { throw 'cargo not found. Run scripts\Prepare-WindowsTestMachine.ps1.' }
Set-Location (Join-Path $Root 'src-tauri')
$old=$ErrorActionPreference
try{$ErrorActionPreference='Continue';& $cargo.Source tauri --version *> $null;$tauriCode=$LASTEXITCODE}
finally{$ErrorActionPreference=$old}
if($tauriCode-ne0){
  Invoke-NativeChecked -FilePath $cargo.Source -ArgumentList @('install','tauri-cli','--version','^2.0','--locked') -Label 'Tauri CLI install'
}
Invoke-NativeChecked -FilePath $cargo.Source -ArgumentList @('tauri','build') -Label 'Tauri build'

# The installer bundles the backend; a raw target\release\metatron.exe does not.
# Copy it for standalone smoke testing without altering installer resources.
$ExeResourceDir = Join-Path $Root 'src-tauri\target\release\resources\metatron-backend'
New-Item -ItemType Directory -Force (Split-Path -Parent $ExeResourceDir) | Out-Null
if (Test-Path $ExeResourceDir) { Remove-Item $ExeResourceDir -Recurse -Force }
Copy-Item (Join-Path $Dist 'metatron-backend') $ExeResourceDir -Recurse -Force
Write-Host 'Metatron build complete. See src-tauri\target\release\bundle.' -ForegroundColor Green
