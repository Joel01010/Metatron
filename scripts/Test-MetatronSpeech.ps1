param([string]$Python='',[string]$OutputDir='',[string]$EngineRoot='')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-speech-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Metatron <-> EZSTT speech integration'
$setup=@{Python=$Python;Verify=$true}
if($EngineRoot){$setup.EngineRoot=$EngineRoot}
& (Join-Path $PSScriptRoot 'Setup-SpeechRuntime.ps1') @setup
$verifyLog=Join-Path $OutputDir 'metatron-speech-placement.log'
$verifyCode=Invoke-TestNative -FilePath $Python -ArgumentList @((Join-Path $PSScriptRoot 'Verify-SpeechRuntime.py'),'--json-out',(Join-Path $OutputDir 'speech-runtime.json')) -Label 'Metatron speech placement verification' -LogPath $verifyLog -AllowFailure
$upstreamDir=Join-Path $OutputDir 'ezstt-upstream'
$upstreamCode=0
try {& (Join-Path $PSScriptRoot 'Invoke-EZSTTQualification.ps1') -Device NPU -OutputDir $upstreamDir}catch{$upstreamCode=2;Write-Error -ErrorAction Continue $_}
$status=if($verifyCode-eq0 -and $upstreamCode-eq0){'PASS'}else{'FAIL'}
$results=@(
    [pscustomobject]@{name='Metatron placement contract';status=$(if($verifyCode-eq0){'PASS'}else{'FAIL'});exit_code=$verifyCode},
    [pscustomobject]@{name='EZSTT protocol focus restart E2E';status=$(if($upstreamCode-eq0){'PASS'}else{'FAIL'});exit_code=$upstreamCode}
)
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'speech' -Status $status -Results $results
if($status-ne'PASS'){throw "Speech qualification failed. Evidence: $OutputDir"}
Write-Host "Speech qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
