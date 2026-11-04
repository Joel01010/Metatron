param(
  [string]$Python = "python",
  [string]$BuildVenv = "Z:\Metatron\build-venv"
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path (Join-Path $BuildVenv 'Scripts\python.exe'))) {
  & $Python -m venv $BuildVenv
}
$Py = Join-Path $BuildVenv 'Scripts\python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install pytest pyinstaller
& $Py -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }

$Dist = Join-Path $Root 'build\backend'
$Work = Join-Path $Root 'build\pyinstaller'
Remove-Item $Dist,$Work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$sep = ';'
& $Py -m PyInstaller --noconfirm --clean --onefile --name metatron-backend `
  --paths $Root `
  --add-data "$(Join-Path $Root 'scripts\kokoro_onnx_worker.py')${sep}scripts" `
  --add-data "$(Join-Path $Root 'scripts\winml_worker.py')${sep}scripts" `
  --distpath $Dist --workpath $Work --specpath $Work `
  (Join-Path $Root 'scripts\backend_entry.py')
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }

$Resources = Join-Path $Root 'src-tauri\resources'
New-Item -ItemType Directory -Force -Path $Resources | Out-Null
Copy-Item (Join-Path $Dist 'metatron-backend.exe') (Join-Path $Resources 'metatron-backend.exe') -Force

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'cargo not found. Install Rust stable-msvc.' }
Set-Location (Join-Path $Root 'src-tauri')
try { cargo tauri --version | Out-Null } catch { cargo install tauri-cli --version '^2.0' --locked }
cargo tauri build
if ($LASTEXITCODE -ne 0) { throw 'Tauri build failed.' }
Write-Host 'Metatron build complete. See src-tauri\target\release\bundle.' -ForegroundColor Green
