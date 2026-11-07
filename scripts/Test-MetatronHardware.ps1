param([string]$Python='',[string]$OutputDir='')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\test-hardware-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
if(-not $Python){$Python=$env:METATRON_TEST_PYTHON}
if(-not $Python -or -not(Test-Path $Python)){throw 'Prepared Metatron test Python missing.'}
Write-TestStage 'Windows hardware / NPU-GPU-CPU / microphone'
& (Join-Path $PSScriptRoot 'Setup-QualificationRuntime.ps1') -Python $Python
& (Join-Path $PSScriptRoot 'Setup-WindowsML.ps1') -Python $Python
$probeModel=Join-Path $OutputDir 'metatron-probe.onnx'
Invoke-TestNative -FilePath $Python -ArgumentList @((Join-Path $PSScriptRoot 'Generate-TestOnnxModel.py'),'--out',$probeModel) -Label 'generate ONNX probe model' -LogPath (Join-Path $OutputDir 'probe-model.log') | Out-Null
$qpy=$env:METATRON_QUALIFICATION_PYTHON
if(-not $qpy -or -not(Test-Path $qpy)){throw 'Qualification Python was not configured.'}
$results=@();$failed=$false
function Run-Hardware([string]$name,[string]$exe,[string[]]$args){
    $log=Join-Path $OutputDir (($name -replace '[^A-Za-z0-9._-]','-')+'.log')
    $code=Invoke-TestNative -FilePath $exe -ArgumentList $args -Label $name -LogPath $log -AllowFailure
    $script:results += [pscustomobject]@{name=$name;status=$(if($code-eq0){'PASS'}else{'FAIL'});exit_code=$code;log=$log}
    if($code-ne0){$script:failed=$true}
}
Run-Hardware 'OpenVINO NPU GPU CPU proof' $qpy @((Join-Path $PSScriptRoot 'Verify-OpenVINODevices.py'),'--require','NPU,GPU,CPU','--json-out',(Join-Path $OutputDir 'openvino-devices.json'))
Run-Hardware 'Microphone capture' $qpy @((Join-Path $PSScriptRoot 'Test-WindowsAudio.py'),'--json-out',(Join-Path $OutputDir 'microphone.json'))
Run-Hardware 'Windows ML catalog' $Python @((Join-Path $PSScriptRoot 'Verify-WindowsML.py'))
Run-Hardware 'Metatron Windows ML placement proof' $Python @((Join-Path $PSScriptRoot 'Verify-Accelerators.py'),'--model',$probeModel,'--report',(Join-Path $OutputDir 'accelerators.json'))
$status=if($failed){'FAIL'}else{'PASS'}
Write-TestSummary -Path (Join-Path $OutputDir 'suite-summary.json') -Name 'hardware' -Status $status -Results $results
if($failed){throw "Hardware qualification failed. Evidence: $OutputDir"}
Write-Host "Hardware qualification PASS. Evidence: $OutputDir" -ForegroundColor Green
