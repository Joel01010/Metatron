param([string]$Python = "python")
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'Rust/cargo is required. Install rustup stable-msvc.' }
& $Python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
$env:METATRON_PYTHON = (Get-Command $Python).Source
Set-Location (Join-Path $Root 'src-tauri')
cargo tauri dev
