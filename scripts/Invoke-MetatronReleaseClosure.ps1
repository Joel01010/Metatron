param(
    [string]$Python='auto',
    [string]$ModelPath='',
    [string]$OutputDir='',
    [string]$EngineRoot='',
    [int]$SoakMinutes=60,
    [switch]$SkipMachinePreparation,
    [switch]$SkipProvisioning,
    [switch]$SkipSpeechModelInstall,
    [switch]$SkipWindowsMLSetup,
    [switch]$RequireSigned
)
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Windows required'}
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
Set-Location $Root
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\final-qualification-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$status='PASS'; $failure=''; $effectivePython=''; $effectiveModel=$ModelPath
try{
    if(-not $SkipMachinePreparation){
        Write-Host '=== Prepare Windows test machine and isolated test Python ===' -ForegroundColor Cyan
        $prepDir=Join-Path $OutputDir 'machine-preparation'
        & $PSScriptRoot\Prepare-WindowsTestMachine.ps1 -Python $Python -OutputDir $prepDir
        $prep=Read-JsonFileSafe (Join-Path $prepDir 'machine-preparation.json')
        if($null-eq$prep -or -not $prep.test_python){throw 'Machine preparation did not return test_python'}
        $effectivePython=[string]$prep.test_python
    }else{
        if($Python -and $Python -ne 'auto' -and (Test-Path $Python)){$effectivePython=[IO.Path]::GetFullPath($Python)}
        else{$effectivePython=Get-PythonExecutable -Requested $Python}
        if(-not $effectivePython){throw 'No usable Python 3.11+ found. Remove -SkipMachinePreparation or pass -Python <path>.'}
    }
    $env:METATRON_TEST_PYTHON=$effectivePython

    if(-not $SkipProvisioning){
        Write-Host '=== Provision qualification OpenVINO/audio runtime ===' -ForegroundColor Cyan
        & $PSScriptRoot\Setup-QualificationRuntime.ps1 -Python $effectivePython

        if(-not $SkipWindowsMLSetup){
            Write-Host '=== Provision Windows ML runtime ===' -ForegroundColor Cyan
            & $PSScriptRoot\Setup-WindowsML.ps1 -Python $effectivePython
        }

        if(-not $effectiveModel){
            $effectiveModel=Join-Path $OutputDir 'metatron-placement-probe.onnx'
            Write-Host '=== Generate local ONNX placement probe ===' -ForegroundColor Cyan
            Invoke-TestNative -FilePath $effectivePython -ArgumentList @((Join-Path $PSScriptRoot 'Generate-TestOnnxModel.py'),'--out',$effectiveModel) -Label 'generate ONNX placement probe' -LogPath (Join-Path $OutputDir 'probe-model.log') | Out-Null
        }

        Write-Host '=== Provision/repair pinned EZSTT + Parakeet + Metatron adapter ===' -ForegroundColor Cyan
        $speechArgs=@{Python=$effectivePython;Verify=$true}
        if($EngineRoot){$speechArgs.EngineRoot=$EngineRoot}
        if($SkipSpeechModelInstall){$speechArgs.SkipModelInstall=$true}
        & $PSScriptRoot\Setup-SpeechRuntime.ps1 @speechArgs

        Write-Host '=== Provision/repair Kokoro premium TTS ===' -ForegroundColor Cyan
        & $PSScriptRoot\Setup-Kokoro-TTS.ps1 -Python $effectivePython -Precision fp16
    }elseif(-not $effectiveModel){
        # Even when provisioning is skipped, create a local probe model when the
        # prepared test environment already has onnx. This removes ModelPath as
        # a human requirement for normal qualification runs.
        $effectiveModel=Join-Path $OutputDir 'metatron-placement-probe.onnx'
        Invoke-TestNative -FilePath $effectivePython -ArgumentList @((Join-Path $PSScriptRoot 'Generate-TestOnnxModel.py'),'--out',$effectiveModel) -Label 'generate ONNX placement probe' -LogPath (Join-Path $OutputDir 'probe-model.log') | Out-Null
    }

    $q=@{
        Python=$effectivePython; SoakMinutes=$SoakMinutes; SetupQualificationRuntime=$true
        RunEZSTTUpstream=$true; RequireSpeechRuntime=$true; RequireKokoro=$true
        OutputDir=$OutputDir
    }
    if($effectiveModel){$q.ModelPath=$effectiveModel}
    if($RequireSigned){$q.RequireSigned=$true}
    & $PSScriptRoot\Invoke-MetatronV14Qualification.ps1 @q

    Write-Host '=== Full Presence/core/companion profile matrix ===' -ForegroundColor Cyan
    & $PSScriptRoot\Test-MetatronPresence.ps1 -Python $effectivePython -OutputDir (Join-Path $OutputDir 'presence-matrix') -SkipBuild
}catch{
    $status='FAIL'; $failure=$_.Exception.Message
    Write-Error -ErrorAction Continue $_
}

# Release inventory is attempted even on failure so the evidence bundle records
# as much of the evaluated environment as possible.
$sbom=Join-Path $OutputDir 'metatron-sbom.json'
$sbomExit=99
if($effectivePython -and (Test-Path $effectivePython)){
    $oldEap=$ErrorActionPreference
    try{
        $ErrorActionPreference='Continue'
        & $effectivePython (Join-Path $PSScriptRoot 'Generate-SBOM.py') --out $sbom
        $sbomExit=$LASTEXITCODE
        if($null-eq$sbomExit){$sbomExit=0}
    }finally{$ErrorActionPreference=$oldEap}
    if($sbomExit-ne0 -and $status-eq'PASS'){$status='FAIL';$failure="SBOM generation failed with exit $sbomExit"}
}else{
    if($status-eq'PASS'){$status='FAIL';$failure='No Python available for SBOM generation'}
}

$validation=Join-Path $OutputDir 'validation-summary.json'
$ezstt=Join-Path $OutputDir 'ezstt\summary.json'
$validationObj=Read-JsonFileSafe $validation
$ezsttObj=Read-JsonFileSafe $ezstt
$summary=Join-Path $OutputDir 'final-closure.json'
[pscustomobject]@{
    schema=4; version='1.4.0'; generated_at=(Get-Date).ToUniversalTime().ToString('o')
    status=$status; failure=$failure
    test_python=$effectivePython
    model_path=$effectiveModel
    windows_validation=$(if($validationObj){$validationObj.overall}else{'UNKNOWN'})
    ezstt=$(if($ezsttObj){$ezsttObj.status}else{'UNKNOWN'})
    speech_runtime_required=$true; kokoro_required=$true; windows_ml_required=$true; soak_minutes=$SoakMinutes
    signature_required=[bool]$RequireSigned; evidence_dir=$OutputDir; sbom=$sbom; sbom_exit=$sbomExit
    presence_screenshot=(Join-Path $OutputDir 'presence-window.png')
    presence_matrix=(Join-Path $OutputDir 'presence-matrix\suite-summary.json')
    product_contract=@{presence_modes=@('orb','pet','both');core_styles=@('solar','lattice','reactor');companion_slots=4;automation_execution='explicit';dashboard_authorized_commands=35;managed_admission_mib=2816}
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summary -Encoding UTF8

# One portable evidence artifact, regardless of PASS/FAIL.
$evidenceZip=$OutputDir+'.zip'
try{
    if(Test-Path $evidenceZip){Remove-Item -LiteralPath $evidenceZip -Force}
    Compress-Archive -Path (Join-Path $OutputDir '*') -DestinationPath $evidenceZip -CompressionLevel Optimal
    Write-Host "Evidence archive: $evidenceZip" -ForegroundColor Cyan
}catch{Write-Warning "Evidence ZIP creation failed: $($_.Exception.Message)"}
if($status-ne'PASS'){throw "Metatron final release closure FAILED: $failure. Evidence: $OutputDir"}
Write-Host "Metatron FINAL release-closure PASS. Evidence: $OutputDir" -ForegroundColor Green
Write-Host "Machine summary: $summary"
