param([string]$Python='',[string]$OutputDir='',[switch]$SkipBuild)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-presence-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Presence / animated core / companions / native window'
$app=Join-Path $Root 'src-tauri\target\release\metatron.exe'
if(-not(Test-Path $app) -and -not $SkipBuild){
    $buildCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Build-Windows.ps1'),'-Python',$Python) -Label 'build before Presence test' -LogPath (Join-Path $OutputDir 'build.log') -AllowFailure
    if($buildCode-ne0){throw "Presence prerequisite build failed. Evidence: $OutputDir"}
}
if(-not(Test-Path $app)){throw "Built Metatron executable not found: $app"}

$old=$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD;$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
try{
    $staticCode=Invoke-TestNative -FilePath $Python -ArgumentList @('-W','error','-m','pytest','-q','tests/test_product_completion.py','tests/test_renderer_single_source.py','tests/test_ui_theme_upgrade.py',"--basetemp=$(Join-Path $OutputDir 'pytest-tmp')") -Label 'Presence regression tests' -LogPath (Join-Path $OutputDir 'presence-pytest.log') -AllowFailure
}finally{$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=$old}

$profileResults=@();$profileFailed=$false
$oldData=$env:METATRON_DATA_DIR
try{
    foreach($profile in @('solar','lattice','reactor','pets','both')){
        $profileData=Join-Path $OutputDir ('profile-data-'+$profile)
        if(Test-Path $profileData){Remove-Item -LiteralPath $profileData -Recurse -Force}
        $cfgLog=Join-Path $OutputDir ('presence-'+$profile+'-configure.log')
        $cfgCode=Invoke-TestNative -FilePath $Python -ArgumentList @((Join-Path $PSScriptRoot 'Configure-TestPresenceProfile.py'),'--data-dir',$profileData,'--profile',$profile) -Label "configure Presence $profile" -LogPath $cfgLog -AllowFailure
        if($cfgCode-ne0){
            $profileResults += [pscustomobject]@{profile=$profile;status='FAIL';stage='configure';exit_code=$cfgCode}
            $profileFailed=$true
            continue
        }
        $env:METATRON_DATA_DIR=$profileData
        $shot=Join-Path $OutputDir ('presence-'+$profile+'.png')
        $probeLog=Join-Path $OutputDir ('presence-'+$profile+'-window.log')
        $probeCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Test-OrbWindow.ps1'),'-AppExe',$app,'-ScreenshotPath',$shot) -Label "Presence $profile native window probe" -LogPath $probeLog -AllowFailure
        $profileResults += [pscustomobject]@{profile=$profile;status=$(if($probeCode-eq0){'PASS'}else{'FAIL'});stage='window';exit_code=$probeCode;screenshot=$shot;log=$probeLog}
        if($probeCode-ne0){$profileFailed=$true}
    }
}finally{$env:METATRON_DATA_DIR=$oldData}

$desktopCode=Invoke-TestNative -FilePath 'powershell' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Measure-MetatronDesktop.ps1'),'-AppExe',$app,'-Python',$Python,'-Scenario','orb_balanced','-OutDir',(Join-Path $OutputDir 'desktop')) -Label 'Presence desktop benchmark' -LogPath (Join-Path $OutputDir 'desktop.log') -AllowFailure
$status=if($staticCode-eq0 -and -not $profileFailed -and $desktopCode-eq0){'PASS'}else{'FAIL'}
$results=@(
 [pscustomobject]@{name='renderer/core/companion regressions';status=$(if($staticCode-eq0){'PASS'}else{'FAIL'});exit_code=$staticCode},
 [pscustomobject]@{name='Presence profile matrix';status=$(if(-not $profileFailed){'PASS'}else{'FAIL'});profiles=$profileResults},
 [pscustomobject]@{name='orb balanced desktop benchmark';status=$(if($desktopCode-eq0){'PASS'}else{'FAIL'});exit_code=$desktopCode}
)
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'presence' -Status $status -Results $results -Extra @{screenshots=@($profileResults | ForEach-Object {$_.screenshot} | Where-Object {$_})}
if($status-ne'PASS'){throw "Presence qualification failed. Evidence: $OutputDir"}
Write-Host "Presence qualification PASS. Five renderer screenshots were captured under $OutputDir" -ForegroundColor Green
