param([string]$Python='',[string]$OutputDir='')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-tts-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Kokoro premium TTS + Windows interruption'
& (Join-Path $PSScriptRoot 'Setup-Kokoro-TTS.ps1') -Python $Python -Precision fp16
$results=@();$failed=$false
function Run-Tts([string]$name,[string[]]$args){
    $log=Join-Path $OutputDir (($name -replace '[^A-Za-z0-9._-]','-')+'.log')
    $code=Invoke-TestNative -FilePath $Python -ArgumentList $args -Label $name -LogPath $log -AllowFailure
    $script:results += [pscustomobject]@{name=$name;status=$(if($code-eq0){'PASS'}else{'FAIL'});exit_code=$code;log=$log}
    if($code-ne0){$script:failed=$true}
}
Run-Tts 'Kokoro benchmark' @((Join-Path $PSScriptRoot 'benchmark_tts.py'))
Run-Tts 'Windows SAPI interruption' @((Join-Path $PSScriptRoot 'Test-WindowsTTSInterrupt.py'))
$status=if($failed){'FAIL'}else{'PASS'}
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'tts' -Status $status -Results $results
if($failed){throw "TTS qualification failed. Evidence: $OutputDir"}
Write-Host "TTS qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
