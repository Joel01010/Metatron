param(
    [ValidateSet('Full','Quick','Portable','Hardware','Speech','TTS','Presence','Automation','Memory','Packaging')]
    [string]$Mode='Full',
    [string]$Python='auto',
    [string]$OutputDir='',
    [int]$SoakMinutes=60,
    [switch]$CheckOnlyPrerequisites,
    [switch]$RequireSigned
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if($env:OS -ne 'Windows_NT'){throw 'Run-MetatronTests.ps1 is intended for Windows 11.'}
Set-Location $Root
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\self-test-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
$started=(Get-Date).ToUniversalTime().ToString('o')
$status='PASS';$failure='';$results=@();$testPython=''

function Run-Suite([string]$name,[string]$file,[hashtable]$params){
    Write-TestStage $name
    try{
        & (Join-Path $PSScriptRoot $file) @params
        $script:results += [pscustomobject]@{name=$name;status='PASS';evidence=$params.OutputDir}
    }catch{
        $script:results += [pscustomobject]@{name=$name;status='FAIL';evidence=$params.OutputDir;error=$_.Exception.Message}
        $script:status='FAIL'
        if(-not $script:failure){$script:failure="${name}: $($_.Exception.Message)"}
        Write-Error -ErrorAction Continue $_
    }
}

try{
    Write-TestStage 'Automatic machine preparation'
    $prepDir=Join-Path $OutputDir '00-machine-preparation'
    $prepArgs=@{Python=$Python;OutputDir=$prepDir}
    if($CheckOnlyPrerequisites){$prepArgs.CheckOnly=$true}
    & (Join-Path $PSScriptRoot 'Prepare-WindowsTestMachine.ps1') @prepArgs
    $prep=Read-JsonFileSafe (Join-Path $prepDir 'machine-preparation.json')
    if($CheckOnlyPrerequisites){
        $results += [pscustomobject]@{name='Machine prerequisites';status='PASS';evidence=$prepDir}
    }else{
        if($null -eq $prep -or -not $prep.test_python){throw 'Machine preparation did not produce a usable test Python.'}
        $testPython=[string]$prep.test_python
        $env:METATRON_TEST_PYTHON=$testPython
        $results += [pscustomobject]@{name='Machine preparation';status='PASS';evidence=$prepDir}

        if($Mode -eq 'Full'){
            Write-TestStage 'Canonical full release closure'
            $closureDir=Join-Path $OutputDir '01-release-closure'
            $args=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Invoke-MetatronReleaseClosure.ps1'),'-Python',$testPython,'-OutputDir',$closureDir,'-SoakMinutes',[string]$SoakMinutes,'-SkipMachinePreparation')
            if($RequireSigned){$args+='-RequireSigned'}
            $code=Invoke-TestNative -FilePath 'powershell' -ArgumentList $args -Label 'Metatron full release closure' -LogPath (Join-Path $OutputDir 'release-closure.log') -AllowFailure
            $results += [pscustomobject]@{name='Full release closure';status=$(if($code-eq0){'PASS'}else{'FAIL'});evidence=$closureDir;exit_code=$code}
            if($code-ne0){$status='FAIL';$failure='Full release closure returned a non-zero exit code.'}
        }elseif($Mode -eq 'Quick'){
            Run-Suite 'Portable' 'Test-MetatronPortable.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-portable')}
            Run-Suite 'Automation' 'Test-MetatronAutomation.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '02-automation')}
        }elseif($Mode -eq 'Portable'){
            Run-Suite 'Portable' 'Test-MetatronPortable.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-portable')}
        }elseif($Mode -eq 'Hardware'){
            Run-Suite 'Hardware' 'Test-MetatronHardware.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-hardware')}
        }elseif($Mode -eq 'Speech'){
            Run-Suite 'Speech' 'Test-MetatronSpeech.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-speech')}
        }elseif($Mode -eq 'TTS'){
            Run-Suite 'TTS' 'Test-MetatronTTS.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-tts')}
        }elseif($Mode -eq 'Presence'){
            Run-Suite 'Presence' 'Test-MetatronPresence.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-presence')}
        }elseif($Mode -eq 'Automation'){
            Run-Suite 'Automation' 'Test-MetatronAutomation.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-automation')}
        }elseif($Mode -eq 'Memory'){
            Run-Suite 'Memory' 'Test-MetatronMemory.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-memory');SoakMinutes=$SoakMinutes}
        }elseif($Mode -eq 'Packaging'){
            Run-Suite 'Packaging' 'Test-MetatronPackaging.ps1' @{Python=$testPython;OutputDir=(Join-Path $OutputDir '01-packaging');RequireSigned=$RequireSigned}
        }
    }
}catch{
    $status='FAIL'
    if(-not $failure){$failure=$_.Exception.Message}
    $results += [pscustomobject]@{name='Harness';status='FAIL';evidence=$OutputDir;error=$_.Exception.Message}
    Write-Error -ErrorAction Continue $_
}

$summary=Join-Path $OutputDir 'SELF-TEST-SUMMARY.json'
[pscustomobject]@{
    schema=2
    product='Metatron'
    version='1.4.0'
    mode=$Mode
    status=$status
    started_at=$started
    completed_at=(Get-Date).ToUniversalTime().ToString('o')
    failure=$failure
    test_python=$testPython
    soak_minutes=$SoakMinutes
    signature_required=[bool]$RequireSigned
    results=$results
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summary -Encoding UTF8

$zip=$OutputDir+'.zip'
try{
    if(Test-Path $zip){Remove-Item -LiteralPath $zip -Force}
    Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $zip -CompressionLevel Optimal
}catch{Write-Warning "Could not create evidence ZIP: $($_.Exception.Message)"}
Write-Host ''
Write-Host "Self-test summary: $summary" -ForegroundColor Cyan
if(Test-Path $zip){Write-Host "Evidence archive: $zip" -ForegroundColor Cyan}
if($status-ne'PASS'){
    Write-Host 'METATRON SELF-TEST: FAIL' -ForegroundColor Red
    exit 2
}
Write-Host 'METATRON SELF-TEST: PASS' -ForegroundColor Green
