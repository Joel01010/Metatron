param([string]$Python='',[string]$OutputDir='',[switch]$RequireSigned)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-packaging-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Windows desktop build / installer / SBOM'
$buildCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Build-Windows.ps1'),'-Python',$Python) -Label 'Windows build' -LogPath (Join-Path $OutputDir 'build.log') -AllowFailure
$artifactArgs=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Verify-WindowsArtifacts.ps1'))
if($RequireSigned){$artifactArgs+='-RequireSigned'}
$artifactCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList $artifactArgs -Label 'artifact verification' -LogPath (Join-Path $OutputDir 'artifacts.log') -AllowFailure
$sbomCode=Invoke-TestNative -FilePath $Python -ArgumentList @((Join-Path $PSScriptRoot 'Generate-SBOM.py'),'--out',(Join-Path $OutputDir 'metatron-sbom.json')) -Label 'SBOM generation' -LogPath (Join-Path $OutputDir 'sbom.log') -AllowFailure
$status=if($buildCode-eq0 -and $artifactCode-eq0 -and $sbomCode-eq0){'PASS'}else{'FAIL'}
$results=@(
 [pscustomobject]@{name='build';status=$(if($buildCode-eq0){'PASS'}else{'FAIL'});exit_code=$buildCode},
 [pscustomobject]@{name='artifacts';status=$(if($artifactCode-eq0){'PASS'}else{'FAIL'});exit_code=$artifactCode},
 [pscustomobject]@{name='sbom';status=$(if($sbomCode-eq0){'PASS'}else{'FAIL'});exit_code=$sbomCode}
)
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'packaging' -Status $status -Results $results -Extra @{signature_required=[bool]$RequireSigned}
if($status-ne'PASS'){throw "Packaging qualification failed. Evidence: $OutputDir"}
Write-Host "Packaging qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
