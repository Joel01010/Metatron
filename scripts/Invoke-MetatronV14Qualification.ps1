param(
  [string]$Python='python',
  [string]$ModelPath='',
  [string]$OutputDir='',
  [int]$SoakMinutes=30,
  [switch]$SetupQualificationRuntime,
  [switch]$RunEZSTTUpstream,
  [switch]$RequireSigned
)
$ErrorActionPreference='Stop';$Root=Split-Path -Parent $PSScriptRoot;Set-Location $Root
if($SetupQualificationRuntime){& $PSScriptRoot\Setup-QualificationRuntime.ps1 -Python $Python;if($LASTEXITCODE-ne0){throw 'Qualification runtime setup failed'};$qroot=if($env:LOCALAPPDATA){Join-Path $env:LOCALAPPDATA 'Metatron\runtimes\qualification\.venv\Scripts\python.exe'}else{''};if($qroot-and(Test-Path$qroot)){$env:METATRON_QUALIFICATION_PYTHON=$qroot}}
if(-not$OutputDir){$OutputDir=Join-Path $Root ('build\v1.4-qualification-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$args=@('-Python',$Python,'-OutputDir',$OutputDir,'-All','-RequireHardware','-SoakMinutes',[string]$SoakMinutes)
if($ModelPath){$args+=@('-ModelPath',$ModelPath)}
if($RequireSigned){$args+='-RequireSigned'}
& $PSScriptRoot\Invoke-MetatronFullValidation.ps1 @args
if($LASTEXITCODE-ne0){throw 'Metatron v1.4 full validation failed'}
if($RunEZSTTUpstream){& $PSScriptRoot\Invoke-EZSTTQualification.ps1 -Device NPU;if($LASTEXITCODE-ne0){throw 'EZSTT upstream qualification failed'}}
Write-Host "Metatron v1.4 qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
