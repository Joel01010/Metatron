param([string]$Python='',[string]$OutputDir='')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-automation-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Automation Center / scheduler / runs / approvals'
$old=$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD;$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
try{
    $log=Join-Path $OutputDir 'automation-pytest.log'
    $args=@('-W','error','-m','pytest','-q','tests/test_product_completion.py','tests/test_scheduler.py','tests/test_runs.py','tests/test_kanban.py','tests/test_product_integration.py',"--basetemp=$(Join-Path $OutputDir 'pytest-tmp')")
    $code=Invoke-TestNative -FilePath $Python -ArgumentList $args -Label 'Automation regression tests' -LogPath $log -AllowFailure
}finally{$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=$old}
$status=if($code-eq0){'PASS'}else{'FAIL'}
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'automation' -Status $status -Extra @{exit_code=$code}
if($code-ne0){throw "Automation regression tests failed. Evidence: $OutputDir"}
Write-Host "Automation regression PASS. Evidence: $OutputDir" -ForegroundColor Green
