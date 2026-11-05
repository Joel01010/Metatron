param(
  [string]$Python = "python",
  [string]$BuildVenv = ""
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
if (-not $BuildVenv) { $BuildVenv = Join-Path $env:LOCALAPPDATA 'Metatron\build-venv' }
Set-Location $Root

if (-not (Test-Path (Join-Path $BuildVenv 'Scripts\python.exe'))) {
  & $Python -m venv $BuildVenv
}
$Py = Join-Path $BuildVenv 'Scripts\python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install pytest pyinstaller
$oldPlugin=$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD;$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
try { & $Python -W error -m pytest tests -q } finally { $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=$oldPlugin }
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
& $Py scripts\product_audit.py
if ($LASTEXITCODE -ne 0) { throw 'Product audit failed.' }

$Dist = Join-Path $Root 'build\backend'
$Work = Join-Path $Root 'build\pyinstaller'
Remove-Item $Dist,$Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$sep = ';'
& $Py -m PyInstaller --noconfirm --clean --onedir --name metatron-backend `
  --paths $Root `
  --add-data "$(Join-Path $Root 'scripts\kokoro_onnx_worker.py')${sep}scripts" `
  --add-data "$(Join-Path $Root 'scripts\winml_worker.py')${sep}scripts" `
  --distpath $Dist --workpath $Work --specpath $Work `
  (Join-Path $Root 'scripts\backend_entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }

$Resources = Join-Path $Root 'src-tauri\resources'
New-Item -ItemType Directory -Force -Path $Resources | Out-Null
Remove-Item (Join-Path $Resources 'metatron-backend') -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Dist 'metatron-backend') (Join-Path $Resources 'metatron-backend') -Recurse -Force

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'cargo not found. Install Rust stable-msvc.' }
Set-Location (Join-Path $Root 'src-tauri')
try { cargo tauri --version | Out-Null } catch { cargo install tauri-cli --version '^2.0' --locked }
cargo tauri build
if ($LASTEXITCODE -ne 0) { throw 'Tauri build failed.' }
# The installer bundles the backend; a raw target\release\metatron.exe does not.
# Copy it for standalone smoke testing without altering installer resources.
$ExeResourceDir = Join-Path $Root 'src-tauri\target\release\resources\metatron-backend'
New-Item -ItemType Directory -Force (Split-Path -Parent $ExeResourceDir) | Out-Null
if (Test-Path $ExeResourceDir) { Remove-Item $ExeResourceDir -Recurse -Force }
Copy-Item (Join-Path $Dist 'metatron-backend') $ExeResourceDir -Recurse -Force
Write-Host 'Metatron build complete. See src-tauri\target\release\bundle.' -ForegroundColor Green
