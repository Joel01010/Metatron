param(
  [string]$EngineRoot = "",
  [string]$Repo = "https://github.com/aurickk/EZSTT.git",
  [string]$Revision = "5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a",
  [string]$Python = "python",
  [switch]$SkipClone
)
$ErrorActionPreference = "Stop"
if (-not $EngineRoot) {
  $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
  $EngineRoot = Join-Path $base "Metatron\engines\EZSTT"
}
$EngineRoot = [IO.Path]::GetFullPath($EngineRoot)
$parent = Split-Path -Parent $EngineRoot
New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (-not (Test-Path $EngineRoot)) {
  if ($SkipClone) { throw "EngineRoot does not exist: $EngineRoot" }
  git clone $Repo $EngineRoot
}
Push-Location $EngineRoot
try {
  if (-not $SkipClone) {
    git fetch --all --tags
    git checkout --detach $Revision
  }
  $venv = Join-Path $EngineRoot "engine\.venv"
  if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) { & $Python -m venv $venv }
  $pip = Join-Path $venv "Scripts\python.exe"
  & $pip -m pip install --upgrade pip
  & $pip -m pip install -r (Join-Path $EngineRoot "engine\requirements.txt")

  Write-Host "EZSTT engine runtime prepared at $EngineRoot"
  Write-Host "Metatron deliberately does not copy EZSTT branding/assets."
  Write-Host "Configure METATRON_SPEECH_CMD to the JSON-lines engine entrypoint used by your pinned EZSTT revision."
  Write-Host "Then run its protocol/CPU smoke tests before enabling auto-start."
} finally { Pop-Location }
