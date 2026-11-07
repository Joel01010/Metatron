param(
    [string]$Python='python',
    [string]$ModelPath='',
    [string]$OutputDir='',
    [int]$SoakMinutes=30,
    [switch]$SetupQualificationRuntime,
    [switch]$RunEZSTTUpstream,
    [switch]$RequireSpeechRuntime,
    [switch]$RequireKokoro,
    [switch]$RequireSigned
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
Set-Location $Root

if($SetupQualificationRuntime){
    & $PSScriptRoot\Setup-QualificationRuntime.ps1 -Python $Python
    $qroot=if($env:LOCALAPPDATA){Join-Path $env:LOCALAPPDATA 'Metatron\runtimes\qualification\.venv\Scripts\python.exe'}else{''}
    if($qroot -and (Test-Path $qroot)){$env:METATRON_QUALIFICATION_PYTHON=$qroot}
}
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\v1.4-qualification-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

# Run the full validator in a child PowerShell process.  Its `exit 2` can then
# never terminate this orchestrator before the independent EZSTT qualification
# has had a chance to collect its evidence.
$fullArgs=@(
    '-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $PSScriptRoot 'Invoke-MetatronFullValidation.ps1'),
    '-Python',$Python,'-OutputDir',$OutputDir,'-All','-RequireHardware','-SoakMinutes',[string]$SoakMinutes
)
if($ModelPath){$fullArgs+=@('-ModelPath',$ModelPath)}
if($RequireSpeechRuntime){$fullArgs+='-RequireSpeechRuntime'}
if($RequireKokoro){$fullArgs+='-RequireKokoro'}
if($RequireSigned){$fullArgs+='-RequireSigned'}
$oldEap=$ErrorActionPreference
try{$ErrorActionPreference='Continue'; & powershell @fullArgs; $fullValidationExit=$LASTEXITCODE}
finally{$ErrorActionPreference=$oldEap}
if($null-eq$fullValidationExit){$fullValidationExit=1}

$ezsttExit=0
if($RunEZSTTUpstream){
    try{
        & $PSScriptRoot\Invoke-EZSTTQualification.ps1 -Device NPU -OutputDir (Join-Path $OutputDir 'ezstt')
    }catch{
        Write-Error -ErrorAction Continue $_
        $ezsttExit=2
    }
}

[pscustomobject]@{
    schema=2
    full_validation_exit=$fullValidationExit
    ezstt_exit=$ezsttExit
    status=$(if($fullValidationExit-eq0 -and $ezsttExit-eq0){'PASS'}else{'FAIL'})
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $OutputDir 'v14-orchestration.json') -Encoding UTF8

if($fullValidationExit-ne0){throw 'Metatron v1.4 full validation failed; inspect the evidence directory'}
if($ezsttExit-ne0){throw 'EZSTT upstream qualification failed; inspect the evidence directory'}
Write-Host "Metatron v1.4 qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
