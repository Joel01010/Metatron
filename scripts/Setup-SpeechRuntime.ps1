param(
  [string]$EngineRoot = "",
  [string]$Repo = "https://github.com/aurickk/EZSTT.git",
  [string]$Revision = "5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a",
  [string]$Python = "python",
  [string]$Model = "parakeet-unified-en-0.6b",
  [ValidateSet("NPU","CPU")][string]$Device = "NPU",
  [switch]$SkipClone,
  [switch]$SkipModelInstall,
  [switch]$Verify
)
$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
  param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [string[]]$ArgumentList = @(),
    [string]$Label = 'native command'
  )
  $oldEap = $ErrorActionPreference
  $code = 1
  try {
    # Windows PowerShell 5.1 can promote a native program's stderr progress
    # output to ErrorRecord objects.  The exit code, not stderr usage, is the
    # authoritative success signal for git/python/pip.
    $ErrorActionPreference = 'Continue'
    & $FilePath @ArgumentList
    $code = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $oldEap
  }
  if ($code -ne 0) { throw "$Label failed with exit $code" }
}

if (-not $EngineRoot) {
  $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME "AppData\Local" }
  $EngineRoot = Join-Path $base "Metatron\engines\EZSTT"
}
$EngineRoot = [IO.Path]::GetFullPath($EngineRoot)
$parent = Split-Path -Parent $EngineRoot
New-Item -ItemType Directory -Force -Path $parent | Out-Null

if (-not (Test-Path $EngineRoot)) {
  if ($SkipClone) { throw "EngineRoot does not exist: $EngineRoot" }
  Invoke-NativeChecked -FilePath 'git' -ArgumentList @('clone',$Repo,$EngineRoot) -Label 'EZSTT git clone'
}
Push-Location $EngineRoot
try {
  if (-not $SkipClone) {
    Invoke-NativeChecked -FilePath 'git' -ArgumentList @('fetch','--all','--tags') -Label 'EZSTT git fetch'
    Invoke-NativeChecked -FilePath 'git' -ArgumentList @('checkout','--detach',$Revision) -Label 'EZSTT git checkout'
  }
  if (Test-Path (Join-Path $EngineRoot '.git')) {
    $oldEap = $ErrorActionPreference
    try {
      $ErrorActionPreference = 'Continue'
      $head = (& git rev-parse HEAD).Trim()
      $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $oldEap }
    if ($code -ne 0) { throw "EZSTT git rev-parse failed with exit $code" }
    if ($head -ne $Revision) { throw "EZSTT revision mismatch: expected $Revision, got $head" }
  }

  $venv = Join-Path $EngineRoot "engine\.venv"
  if (-not (Test-Path (Join-Path $venv 'Scripts\python.exe'))) {
    Invoke-NativeChecked -FilePath $Python -ArgumentList @('-m','venv',$venv) -Label 'EZSTT venv creation'
  }
  $py = Join-Path $venv "Scripts\python.exe"
  Invoke-NativeChecked -FilePath $py -ArgumentList @('-m','pip','install','--upgrade','pip') -Label 'EZSTT pip upgrade'
  Invoke-NativeChecked -FilePath $py -ArgumentList @('-m','pip','install','-r',(Join-Path $EngineRoot 'engine\requirements.txt')) -Label 'EZSTT dependency install'

  # Install Metatron's thin compatibility entrypoint next to the pinned engine.
  # It imports EZSTT in-process; it does not spawn a second STT runtime.
  $bridgeSource = Join-Path $PSScriptRoot 'ezstt_metatron_sidecar.py'
  if (-not (Test-Path $bridgeSource)) { throw "Metatron EZSTT adapter missing: $bridgeSource" }
  $bridge = Join-Path $EngineRoot 'metatron_sidecar.py'
  Copy-Item -LiteralPath $bridgeSource -Destination $bridge -Force
  Invoke-NativeChecked -FilePath $py -ArgumentList @('-m','py_compile',$bridge) -Label 'Metatron EZSTT adapter syntax check'

  $command = @($py, $bridge, '--engine-root', $EngineRoot)
  $runtimeRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Metatron\runtimes' } else { Join-Path $HOME 'AppData\Local\Metatron\runtimes' }
  New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
  $manifest = Join-Path $runtimeRoot 'speech-command.json'
  @{
    schema = 2
    engine = 'EZSTT'
    revision = $Revision
    model = $Model
    requested_device = $Device
    command = $command
    installed_at = (Get-Date).ToUniversalTime().ToString('o')
  } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding UTF8

  # Keep the documented environment override wired as well. Every argument is
  # quoted; metatron.speech._split_command removes the outer quotes on Windows.
  $commandLine = (($command | ForEach-Object { '"' + ([string]$_).Replace('"','\"') + '"' }) -join ' ')
  $env:METATRON_SPEECH_CMD = $commandLine
  [Environment]::SetEnvironmentVariable('METATRON_SPEECH_CMD', $commandLine, 'User')

  $modelPath = Join-Path (Join-Path $EngineRoot 'models') $Model
  if (-not $SkipModelInstall) {
    $provision = Join-Path $PSScriptRoot 'Provision-EZSTTModel.py'
    if (-not (Test-Path $provision)) { throw "EZSTT model provisioner missing: $provision" }
    Invoke-NativeChecked -FilePath $py -ArgumentList @($provision,'--engine-root',$EngineRoot,'--python',$py,'--model',$Model,'--device',$Device,'--timeout','3600') -Label 'EZSTT model provisioning'
  } elseif (-not (Test-Path $modelPath)) {
    Write-Warning "Speech model is absent at $modelPath and -SkipModelInstall was requested."
  }

  if ($Verify) {
    Invoke-NativeChecked -FilePath $Python -ArgumentList @((Join-Path $PSScriptRoot 'Verify-SpeechRuntime.py')) -Label 'Metatron-EZSTT verification'
  }

  Write-Host "EZSTT engine runtime prepared at $EngineRoot" -ForegroundColor Green
  Write-Host "Pinned revision: $Revision"
  Write-Host "Model: $Model ($Device requested; placement is verified at runtime)"
  Write-Host "Metatron adapter: $bridge"
  Write-Host "Command manifest: $manifest"
  Write-Host "METATRON_SPEECH_CMD is active in this process and persisted for future user sessions."
} finally { Pop-Location }
