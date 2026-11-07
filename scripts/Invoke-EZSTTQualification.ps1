param(
    [string]$EngineRoot="",
    [ValidateSet('NPU','CPU')][string]$Device='NPU',
    [string]$OutputDir='',
    [switch]$InstalledTest,
    [switch]$SkipDebugBuild
)
$ErrorActionPreference='Stop'

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$ArgumentList=@(),
        [string]$Label='native command',
        [string]$LogPath=''
    )
    $oldEap=$ErrorActionPreference; $code=1
    try {
        $ErrorActionPreference='Continue'
        if($LogPath){ & $FilePath @ArgumentList 2>&1 | Tee-Object -FilePath $LogPath }
        else { & $FilePath @ArgumentList }
        $code=$LASTEXITCODE
    } finally { $ErrorActionPreference=$oldEap }
    if($code-ne0){throw "$Label failed with exit $code"}
    return $code
}

if(-not $EngineRoot){
    $base=if($env:LOCALAPPDATA){$env:LOCALAPPDATA}else{Join-Path $HOME 'AppData\Local'}
    $EngineRoot=Join-Path $base 'Metatron\engines\EZSTT'
}
$EngineRoot=[IO.Path]::GetFullPath($EngineRoot)
$Py=Join-Path $EngineRoot 'engine\.venv\Scripts\python.exe'
if(-not(Test-Path $Py)){throw "EZSTT venv missing: $Py"}
$tests=Join-Path $EngineRoot 'tests'
if(-not(Test-Path $tests)){throw "EZSTT tests missing: $tests"}

$debugExe=Join-Path $EngineRoot 'src-tauri\target\debug\ezstt.exe'
if(-not(Test-Path $debugExe)){
    if($SkipDebugBuild){throw "EZSTT debug shell missing: $debugExe"}
    if(-not(Get-Command npm -ErrorAction SilentlyContinue)){throw 'npm is required to build the EZSTT debug shell'}
    if(-not(Get-Command cargo -ErrorAction SilentlyContinue)){throw 'cargo is required to build the EZSTT debug shell'}
    Push-Location $EngineRoot
    try{
        if(-not(Test-Path (Join-Path $EngineRoot 'node_modules'))){
            Write-Host '=== EZSTT npm ci ==='
            Invoke-NativeChecked -FilePath 'npm' -ArgumentList @('ci') -Label 'EZSTT npm ci' | Out-Null
        }
        Write-Host '=== EZSTT debug Tauri build ==='
        Invoke-NativeChecked -FilePath 'npm' -ArgumentList @('run','tauri','build','--','--debug','--no-bundle') -Label 'EZSTT debug build' | Out-Null
    } finally {Pop-Location}
    if(-not(Test-Path $debugExe)){throw "EZSTT debug build completed but executable is missing: $debugExe"}
}

if($OutputDir){New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null}
$results=@(); $old=$env:EZSTT_TEST_DEVICE; $env:EZSTT_TEST_DEVICE=$Device
try{
    $suite=@('test_protocol.py','test_focus.py','test_restart.py','test_e2e.py')
    if($InstalledTest){$suite+='test_installed.py'}
    foreach($name in $suite){
        $path=Join-Path $tests $name
        if(-not(Test-Path $path)){throw "Pinned EZSTT test missing: $name"}
        Write-Host "=== EZSTT $name ($Device) ==="
        $log=if($OutputDir){Join-Path $OutputDir ($name+'.log')}else{''}
        try {
            Invoke-NativeChecked -FilePath $Py -ArgumentList @($path) -Label $name -LogPath $log | Out-Null
            $code=0; $status='PASS'
        } catch {
            $code=if($LASTEXITCODE){$LASTEXITCODE}else{1}; $status='FAIL'
            $results += [pscustomobject]@{name=$name;exit_code=$code;status=$status;log=$log}
            throw
        }
        $results += [pscustomobject]@{name=$name;exit_code=$code;status=$status;log=$log}
    }
}finally{$env:EZSTT_TEST_DEVICE=$old}
if($OutputDir){
    [pscustomobject]@{schema=2;device=$Device;engine_root=$EngineRoot;status='PASS';tests=$results} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDir 'summary.json') -Encoding UTF8
}
Write-Host 'EZSTT upstream qualification PASS' -ForegroundColor Green
