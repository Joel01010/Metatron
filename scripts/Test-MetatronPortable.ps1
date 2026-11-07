param([string]$Python='',[string]$OutputDir='')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-portable-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing. Run Prepare-WindowsTestMachine.ps1 first.'}
Write-TestStage 'Portable + static + Rust/Tauri checks'
$log=Join-Path $OutputDir 'portable-validation.log'
$code=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Invoke-MetatronFullValidation.ps1'),'-Python',$Python,'-OutputDir',$OutputDir,'-SkipAccelerators','-SkipSpeech','-SkipTTS') -Label 'portable validation' -LogPath $log -AllowFailure
$status=if($code -eq 0){'PASS'}else{'FAIL'}
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'portable' -Status $status -Extra @{exit_code=$code}
if($code -ne 0){throw "Portable validation failed. Evidence: $OutputDir"}
Write-Host "Portable validation PASS. Evidence: $OutputDir" -ForegroundColor Green
