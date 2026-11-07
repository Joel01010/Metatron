param([string]$Python='',[string]$OutputDir='',[int]$SoakMinutes=60,[switch]$SkipBuild)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-memory-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
if($SoakMinutes -lt 1){throw 'SoakMinutes must be at least 1.'}
Write-TestStage "Memory / leak / $SoakMinutes-minute soak"
$app=Join-Path $Root 'src-tauri\target\release\metatron.exe'
if(-not(Test-Path $app) -and -not $SkipBuild){
    $code=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Build-Windows.ps1'),'-Python',$Python) -Label 'build before memory test' -LogPath (Join-Path $OutputDir 'build.log') -AllowFailure
    if($code-ne0){throw "Memory test prerequisite build failed. Evidence: $OutputDir"}
}
if(-not(Test-Path $app)){throw "Built Metatron executable not found: $app"}
$idleCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Measure-MetatronDesktop.ps1'),'-AppExe',$app,'-Python',$Python,'-Scenario','idle_shell','-OutDir',(Join-Path $OutputDir 'idle')) -Label 'idle desktop benchmark' -LogPath (Join-Path $OutputDir 'idle.log') -AllowFailure
$soakCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Measure-MetatronSoak.ps1'),'-AppExe',$app,'-Python',$Python,'-DurationMinutes',[string]$SoakMinutes,'-OutDir',(Join-Path $OutputDir 'soak')) -Label 'long memory soak' -LogPath (Join-Path $OutputDir 'soak.log') -AllowFailure
$status=if($idleCode-eq0 -and $soakCode-eq0){'PASS'}else{'FAIL'}
$results=@(
 [pscustomobject]@{name='idle desktop';status=$(if($idleCode-eq0){'PASS'}else{'FAIL'});exit_code=$idleCode},
 [pscustomobject]@{name='long soak';status=$(if($soakCode-eq0){'PASS'}else{'FAIL'});exit_code=$soakCode}
)
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'memory' -Status $status -Results $results -Extra @{soak_minutes=$SoakMinutes;strict_admission_mib=2816}
if($status-ne'PASS'){throw "Memory qualification failed. Evidence: $OutputDir"}
Write-Host "Memory qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
