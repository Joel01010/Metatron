param([string]$EngineRoot="",[ValidateSet('NPU','CPU')][string]$Device='NPU',[switch]$InstalledTest)
$ErrorActionPreference='Stop';if(-not$EngineRoot){$base=if($env:LOCALAPPDATA){$env:LOCALAPPDATA}else{Join-Path $HOME 'AppData\Local'};$EngineRoot=Join-Path $base 'Metatron\engines\EZSTT'}
$Py=Join-Path $EngineRoot 'engine\.venv\Scripts\python.exe';if(-not(Test-Path $Py)){throw "EZSTT venv missing: $Py"};$tests=Join-Path $EngineRoot 'tests';if(-not(Test-Path $tests)){throw "EZSTT tests missing: $tests"}
$old=$env:EZSTT_TEST_DEVICE;$env:EZSTT_TEST_DEVICE=$Device
try{
  $suite=@('test_protocol.py','test_focus.py','test_restart.py','test_e2e.py')
  if($InstalledTest){$suite+='test_installed.py'}
  foreach($name in $suite){$path=Join-Path $tests $name;if(-not(Test-Path $path)){throw "Pinned EZSTT test missing: $name"};Write-Host "=== EZSTT $name ($Device) ===";& $Py $path;if($LASTEXITCODE-ne0){throw "$name failed with exit $LASTEXITCODE"}}
}finally{$env:EZSTT_TEST_DEVICE=$old}
Write-Host 'EZSTT upstream qualification PASS'
