param(
    [string]$Python='auto',
    [string]$OutputDir='',
    [switch]$CheckOnly,
    [switch]$SkipVisualStudioInstall
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot '_TestHarness.ps1')
if($env:OS -ne 'Windows_NT'){throw 'Metatron release qualification requires Windows 11.'}
if(-not $OutputDir){$OutputDir=Join-Path $Root ('build\machine-prep-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
$OutputDir=Ensure-TestDirectory $OutputDir
Set-Location $Root

Write-TestStage 'Machine prerequisites and test runtime'
$checks=@()
function Add-Check([string]$name,[bool]$ok,[string]$detail){
    $script:checks += [pscustomobject]@{name=$name;ok=$ok;detail=$detail}
    Write-Host "[$(if($ok){'PASS'}else{'FAIL'})] $name - $detail" -ForegroundColor $(if($ok){'Green'}else{'Red'})
}
function Install-WingetPackage([string]$Id,[string[]]$ExtraArgs=@()){
    if($CheckOnly){return}
    $winget=Get-Command winget -ErrorAction SilentlyContinue
    if(-not $winget){throw "winget is required to automatically install $Id. Install Microsoft App Installer, then rerun TEST-METATRON.cmd."}
    $args=@('install','--id',$Id,'-e','--source','winget','--accept-package-agreements','--accept-source-agreements','--disable-interactivity')
    $args += $ExtraArgs
    Invoke-TestNative -FilePath $winget.Source -ArgumentList $args -Label "install $Id" -LogPath (Join-Path $OutputDir (($Id -replace '[^A-Za-z0-9._-]','-')+'.log')) | Out-Null
    Refresh-ProcessPath
}
function Ensure-Command([string]$Name,[string]$PackageId){
    $cmd=Get-Command $Name -ErrorAction SilentlyContinue
    if(-not $cmd -and -not $CheckOnly){
        Write-Host "Installing missing tool: $Name ($PackageId)" -ForegroundColor Yellow
        Install-WingetPackage $PackageId
        $cmd=Get-Command $Name -ErrorAction SilentlyContinue
    }
    Add-Check $Name ([bool]$cmd) $(if($cmd){$cmd.Source}else{'not found'})
    return $cmd
}

$os=Get-CimInstance Win32_OperatingSystem
$build=[int]$os.BuildNumber
Add-Check 'Windows 11' ($build -ge 22000) ("{0} build {1}" -f $os.Caption,$build)
if($build -lt 22000){throw 'Windows 11 build 22000 or later is required.'}

Refresh-ProcessPath
$pythonExe=Get-PythonExecutable -Requested $Python
if(-not $pythonExe -and -not $CheckOnly){
    Write-Host 'Installing Python 3.12...' -ForegroundColor Yellow
    Install-WingetPackage 'Python.Python.3.12'
    $pythonExe=Get-PythonExecutable -Requested 'auto'
}
Add-Check 'Python >= 3.11' ([bool]$pythonExe) $(if($pythonExe){$pythonExe}else{'not found'})
if(-not $pythonExe){throw 'Python 3.11+ is required and could not be prepared.'}

$git=Ensure-Command 'git' 'Git.Git'
$node=Ensure-Command 'node' 'OpenJS.NodeJS.LTS'
$npm=Get-Command npm -ErrorAction SilentlyContinue
Add-Check 'npm' ([bool]$npm) $(if($npm){$npm.Source}else{'not found'})
if(-not $npm -and -not $CheckOnly){throw 'Node.js installed without npm; repair Node.js and rerun.'}

$cargo=Get-Command cargo -ErrorAction SilentlyContinue
if(-not $cargo -and -not $CheckOnly){
    Write-Host 'Installing Rustup...' -ForegroundColor Yellow
    Install-WingetPackage 'Rustlang.Rustup'
    Refresh-ProcessPath
    $cargo=Get-Command cargo -ErrorAction SilentlyContinue
}
Add-Check 'cargo' ([bool]$cargo) $(if($cargo){$cargo.Source}else{'not found'})
if(-not $cargo){throw 'Rust/Cargo is required and could not be prepared.'}
if(-not $CheckOnly){
    $rustup=Get-Command rustup -ErrorAction SilentlyContinue
    if($rustup){
        Invoke-TestNative -FilePath $rustup.Source -ArgumentList @('default','stable-x86_64-pc-windows-msvc') -Label 'select stable MSVC Rust toolchain' -LogPath (Join-Path $OutputDir 'rustup-default.log') | Out-Null
        Invoke-TestNative -FilePath $rustup.Source -ArgumentList @('target','add','x86_64-pc-windows-msvc') -Label 'install Rust MSVC target' -LogPath (Join-Path $OutputDir 'rustup-target.log') | Out-Null
    }
}

$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
function Get-VcInstallPath {
    if(-not(Test-Path $vswhere)){return ''}
    $old=$ErrorActionPreference
    try{
        $ErrorActionPreference='Continue'
        return [string]((& $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null | Select-Object -First 1))
    }finally{$ErrorActionPreference=$old}
}
function Get-AnyVsInstallPath {
    if(-not(Test-Path $vswhere)){return ''}
    $old=$ErrorActionPreference
    try{
        $ErrorActionPreference='Continue'
        return [string]((& $vswhere -latest -products * -property installationPath 2>$null | Select-Object -First 1))
    }finally{$ErrorActionPreference=$old}
}
$vcPath=Get-VcInstallPath
if(-not $vcPath -and -not $CheckOnly -and -not $SkipVisualStudioInstall){
    $anyVs=Get-AnyVsInstallPath
    if(-not $anyVs){
        Write-Host 'Installing Visual Studio 2022 Build Tools (C++ workload). This can trigger UAC.' -ForegroundColor Yellow
        Install-WingetPackage 'Microsoft.VisualStudio.2022.BuildTools' @('--override','--wait --passive --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
        $anyVs=Get-AnyVsInstallPath
    }
    $vcPath=Get-VcInstallPath
    if(-not $vcPath -and $anyVs){
        # WinGet may decline to modify an existing Build Tools instance. Repair
        # that instance explicitly through the Visual Studio Installer.
        $vsSetup=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\setup.exe'
        if(Test-Path $vsSetup){
            Write-Host 'Adding the Visual C++ workload to the existing Visual Studio instance...' -ForegroundColor Yellow
            Invoke-TestNative -FilePath $vsSetup -ArgumentList @('modify','--installPath',$anyVs,'--add','Microsoft.VisualStudio.Workload.VCTools','--includeRecommended','--passive','--norestart') -Label 'add Visual C++ build workload' -LogPath (Join-Path $OutputDir 'visual-studio-modify.log') | Out-Null
            $vcPath=Get-VcInstallPath
        }
    }
}
Add-Check 'MSVC C++ Build Tools' ([bool]$vcPath) $(if($vcPath){[string]$vcPath}else{'not found'})
if(-not $vcPath -and -not $SkipVisualStudioInstall){throw 'Visual Studio C++ Build Tools are required for the Tauri Windows build.'}

$webViewRoots=@(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\EdgeWebView\Application'),
    (Join-Path $env:ProgramFiles 'Microsoft\EdgeWebView\Application'),
    (Join-Path $env:LOCALAPPDATA 'Microsoft\EdgeWebView\Application')
) | Where-Object {$_ -and (Test-Path $_)}
if($webViewRoots.Count -eq 0 -and -not $CheckOnly){
    Write-Host 'Installing Microsoft Edge WebView2 Runtime...' -ForegroundColor Yellow
    Install-WingetPackage 'Microsoft.EdgeWebView2Runtime'
    $webViewRoots=@(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\EdgeWebView\Application'),
        (Join-Path $env:ProgramFiles 'Microsoft\EdgeWebView\Application'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\EdgeWebView\Application')
    ) | Where-Object {$_ -and (Test-Path $_)}
}
Add-Check 'WebView2 Runtime' ($webViewRoots.Count -gt 0) $(if($webViewRoots.Count){$webViewRoots -join '; '}else{'not found'})
if($webViewRoots.Count -eq 0){throw 'WebView2 Runtime is required.'}

$runtimeRoot=Ensure-TestDirectory (Join-Path $Root 'build\test-runtime')
$venv=Join-Path $runtimeRoot '.venv'
$testPython=Join-Path $venv 'Scripts\python.exe'
if(-not $CheckOnly){
    if(-not(Test-Path $testPython)){
        Invoke-TestNative -FilePath $pythonExe -ArgumentList @('-m','venv',$venv) -Label 'create Metatron test venv' -LogPath (Join-Path $OutputDir 'venv-create.log') | Out-Null
    }
    Invoke-TestNative -FilePath $testPython -ArgumentList @('-m','pip','install','--upgrade','pip','setuptools','wheel') -Label 'upgrade test venv packaging tools' -LogPath (Join-Path $OutputDir 'pip-upgrade.log') | Out-Null
    Invoke-TestNative -FilePath $testPython -ArgumentList @('-m','pip','install','-e','.[dev]','onnx') -Label 'install Metatron test dependencies' -LogPath (Join-Path $OutputDir 'pip-metatron-dev.log') | Out-Null
}
Add-Check 'Metatron test Python' (Test-Path $testPython) $testPython
if(-not(Test-Path $testPython)){throw 'Metatron test venv could not be prepared.'}

$env:METATRON_TEST_PYTHON=$testPython
$manifest=Join-Path $OutputDir 'machine-preparation.json'
[pscustomobject]@{
    schema=2
    status='PASS'
    generated_at=(Get-Date).ToUniversalTime().ToString('o')
    root=$Root
    python=$pythonExe
    test_python=$testPython
    visual_studio=$vcPath
    webview2=$webViewRoots
    checks=$checks
} | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $manifest -Encoding UTF8
Write-Host "Machine preparation PASS. Test Python: $testPython" -ForegroundColor Green
Write-Host "Preparation manifest: $manifest"
