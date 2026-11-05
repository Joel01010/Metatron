param(
  [string]$Python="python",
  [string]$ModelPath="",
  [string]$OutputDir="",
  [switch]$All,
  [switch]$Build,
  [switch]$DesktopBenchmark,
  [switch]$SkipAccelerators,
  [switch]$SkipSpeech,
  [switch]$SkipTTS,
  [switch]$SupportBundle,
  [switch]$RequireHardware,
  [switch]$RequireSigned,
  [int]$SoakMinutes=0
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
if(-not$OutputDir){$OutputDir=Join-Path $Root "build\validation-$stamp"}
New-Item -ItemType Directory -Force $OutputDir|Out-Null
Set-Location $Root
$results=@();$overall=$true
function Add($n,$s,$d,$log=''){$script:results+=[pscustomobject]@{name=$n;status=$s;detail=$d;log=$log};if($s-eq'FAIL'){$script:overall=$false};Write-Host "[$s] $n - $d"}
function Run($n,$exe,$argList,$optional=$false){
  $log=Join-Path $OutputDir (($n-replace'[^A-Za-z0-9._-]','-').ToLower()+'.log')
  try{$prior=$ErrorActionPreference;try{$ErrorActionPreference='Continue';& $exe @argList 2>&1|Tee-Object $log|Out-Host}finally{$ErrorActionPreference=$prior};$c=$LASTEXITCODE;if($null-eq$c){$c=0};if($c-eq0){Add $n PASS 'exit 0' $log}elseif($optional){Add $n WARN "exit $c" $log}else{Add $n FAIL "exit $c" $log}}
  catch{if($optional){Add $n WARN $_.Exception.Message $log}else{Add $n FAIL $_.Exception.Message $log}}
}

@{schema=1;version='1.4.0';generated_at=(Get-Date).ToUniversalTime().ToString('o');os=Get-CimInstance Win32_OperatingSystem;cpu=Get-CimInstance Win32_Processor;display=Get-CimInstance Win32_VideoController}|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 (Join-Path $OutputDir 'system-inventory.json')
Add 'System inventory' PASS 'captured'
Run 'PowerShell parse and metrics smoke' powershell @('-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\Test-PowerShellScripts.ps1','-Python',$Python)
$old=$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD;$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1';try{Run 'Pytest canonical' $Python @('-W','error','-m','pytest','-q')}finally{$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD=$old}
Run 'Python compile' $Python @('-m','compileall','-q','metatron','scripts','tests')
Run 'Product audit' $Python @('scripts\product_audit.py','--json-out',(Join-Path $OutputDir 'product-audit.json'))
Run 'Core benchmark' $Python @('scripts\benchmark_core.py','--samples','100','--json-out',(Join-Path $OutputDir 'core-benchmark.json'))
if(Get-Command node -EA SilentlyContinue){Run 'UI syntax app' node @('--check','ui\app.js');Run 'UI syntax orb' node @('--check','ui\orb.js');Run 'UI syntax renderer' node @('--check','ui\orb-renderer.js')}
if(Get-Command cargo -EA SilentlyContinue){Push-Location src-tauri;try{Run 'Rust fmt' cargo @('fmt','--','--check');Run 'Tauri cargo check' cargo @('check')}finally{Pop-Location}}else{Add 'Tauri cargo check' WARN 'cargo not installed'}

if(-not$SkipAccelerators){
  $a=@('scripts\Verify-Accelerators.py','--report',(Join-Path $OutputDir 'accelerators.json'));if($ModelPath){$a+=@('--model',$ModelPath)};Run 'Windows ML routing/proof' $Python $a ((!$ModelPath)-and(!$RequireHardware))
  $qpy=$env:METATRON_QUALIFICATION_PYTHON
  if($qpy -and (Test-Path $qpy)){Run 'OpenVINO NPU/GPU/CPU proof' $qpy @('scripts\Verify-OpenVINODevices.py','--require',$(if($RequireHardware){'NPU,GPU,CPU'}else{'CPU'}),'--json-out',(Join-Path $OutputDir 'openvino-devices.json')) (!$RequireHardware)}else{Add 'OpenVINO NPU/GPU/CPU proof' $(if($RequireHardware){'FAIL'}else{'SKIP'}) 'METATRON_QUALIFICATION_PYTHON not configured'}
}

if(-not$SkipSpeech){
  if($env:METATRON_SPEECH_CMD){Run 'Speech runtime placement' $Python @('scripts\Verify-SpeechRuntime.py','--json-out',(Join-Path $OutputDir 'speech.json')) (!$RequireHardware)}else{Add 'Speech runtime placement' $(if($RequireHardware){'FAIL'}else{'SKIP'}) 'METATRON_SPEECH_CMD not configured'}
  $qpy=$env:METATRON_QUALIFICATION_PYTHON;if($qpy -and(Test-Path $qpy)){Run 'Microphone endpoint capture' $qpy @('scripts\Test-WindowsAudio.py','--json-out',(Join-Path $OutputDir 'audio.json')) (!$RequireHardware)}else{Add 'Microphone endpoint capture' $(if($RequireHardware){'FAIL'}else{'SKIP'}) 'qualification runtime not configured'}
}

if(-not$SkipTTS){
  if($env:METATRON_KOKORO_PYTHON){Run 'Kokoro TTS benchmark' $Python @('scripts\benchmark_tts.py') $true}else{Add 'Kokoro TTS benchmark' SKIP 'Kokoro not configured'}
  Run 'Windows SAPI playback interruption' $Python @('scripts\Test-WindowsTTSInterrupt.py') (!$RequireHardware)
}

if($Build-or$All){
  Run 'Windows desktop build' powershell @('-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\Build-Windows.ps1','-Python',$Python)
  if($overall){$artifactArgs=@('-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\Verify-WindowsArtifacts.ps1');if($RequireSigned){$artifactArgs+='-RequireSigned'};Run 'Installer/signature verification' powershell $artifactArgs $false}
}

if(($DesktopBenchmark-or$All)-and$overall){
  try{& $PSScriptRoot\Measure-MetatronDesktop.ps1 -Python $Python -Scenario idle_shell -OutDir (Join-Path $OutputDir 'desktop');if($LASTEXITCODE-ne0){throw 'Desktop measurement failed'};Add 'Desktop idle benchmark' PASS 'captured'}catch{Add 'Desktop idle benchmark' WARN $_.Exception.Message}
  try{& $PSScriptRoot\Test-OrbWindow.ps1; if($LASTEXITCODE-ne0){throw 'Orb visibility/bounds failed'};Add 'Orb visibility and bounds' PASS 'visible and intersects a monitor'}catch{Add 'Orb visibility and bounds' $(if($RequireHardware){'FAIL'}else{'WARN'}) $_.Exception.Message}
}
if($SoakMinutes -gt 0 -and $overall){Run 'Long-duration memory soak' powershell @('-NoProfile','-ExecutionPolicy','Bypass','-File','scripts\Measure-MetatronSoak.ps1','-Python',$Python,'-DurationMinutes',[string]$SoakMinutes,'-OutDir',(Join-Path $OutputDir 'soak')) $false}
if($SupportBundle-or$All){try{& $PSScriptRoot\Collect-SupportBundle.ps1 -OutFile (Join-Path $OutputDir 'Metatron-Support.zip');Add 'Support bundle' PASS 'generated'}catch{Add 'Support bundle' WARN $_.Exception.Message}}
@{schema=2;version='1.4.0';overall=if($overall){'PASS'}else{'FAIL'};results=$results}|ConvertTo-Json -Depth 7|Set-Content -Encoding UTF8 (Join-Path $OutputDir 'validation-summary.json')
if(-not$overall){exit 2}
