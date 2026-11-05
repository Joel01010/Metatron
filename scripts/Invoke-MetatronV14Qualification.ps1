param(
    [string]$Python='python',
    [string]$ModelPath='',
    [string]$OutputDir='',
    [int]$SoakMinutes=30,
    [switch]$SetupQualificationRuntime,
    [switch]$RunEZSTTUpstream,
    [switch]$RequireSpeechRuntime,
    [switch]$RequireSigned
)

$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
Set-Location $Root

if($SetupQualificationRuntime){
    & $PSScriptRoot\Setup-QualificationRuntime.ps1 -Python $Python
    if($LASTEXITCODE -ne 0){throw 'Qualification runtime setup failed'}
    $qroot=if($env:LOCALAPPDATA){
        Join-Path $env:LOCALAPPDATA 'Metatron\runtimes\qualification\.venv\Scripts\python.exe'
    }else{''}
    if($qroot -and (Test-Path $qroot)){
        $env:METATRON_QUALIFICATION_PYTHON=$qroot
    }
}

if(-not $OutputDir){
    $OutputDir=Join-Path $Root ('build\v1.4-qualification-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
}

$fwd=@(
    '-Python',$Python,
    '-OutputDir',$OutputDir,
    '-All',
    '-RequireHardware',
    '-SoakMinutes',[string]$SoakMinutes
)
if($ModelPath){$fwd+=@('-ModelPath',$ModelPath)}
if($RequireSpeechRuntime){$fwd+='-RequireSpeechRuntime'}
if($RequireSigned){$fwd+='-RequireSigned'}

& $PSScriptRoot\Invoke-MetatronFullValidation.ps1 @fwd
$fullValidationExit=$LASTEXITCODE

# Run upstream EZSTT qualification independently so a failure elsewhere does not hide STT evidence.
$ezsttExit=0
if($RunEZSTTUpstream){
    try {
        & $PSScriptRoot\Invoke-EZSTTQualification.ps1 -Device NPU
        if($LASTEXITCODE -ne 0){$ezsttExit=$LASTEXITCODE}
    } catch {
        Write-Error $_
        $ezsttExit=2
    }
}

if($fullValidationExit -ne 0){throw 'Metatron v1.4 full validation failed; inspect the evidence directory'}
if($ezsttExit -ne 0){throw 'EZSTT upstream qualification failed'}
Write-Host "Metatron v1.4 qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
