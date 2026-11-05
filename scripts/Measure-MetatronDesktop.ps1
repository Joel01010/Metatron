param(
    [string]$AppExe="",
    [int]$WarmupSeconds=8,
    [int]$MeasureSeconds=30,
    [ValidateSet("idle_shell","certified_core","orb_balanced","orb_eco")][string]$Scenario="idle_shell",
    [string]$Python="python",
    [string]$OutDir="",
    [switch]$SkipGpu
)

$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
if(-not $OutDir){$OutDir=Join-Path $Root 'build\desktop-benchmark'}
New-Item -ItemType Directory -Force $OutDir | Out-Null
if(-not $AppExe){
    $AppExe=@(
        (Join-Path $Root 'src-tauri\target\release\metatron.exe'),
        (Join-Path $Root 'src-tauri\target\release\Metatron.exe')
    ) | Where-Object {Test-Path $_} | Select-Object -First 1
}
if(-not $AppExe){throw 'Built Metatron executable not found'}

$before=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$p=Start-Process $AppExe -PassThru
$measureStarted=Get-Date
try {
    Start-Sleep $WarmupSeconds
    if($p.HasExited){throw "Metatron exited: $($p.ExitCode)"}
    $metrics=Join-Path $OutDir 'desktop-metrics.json'
    & $PSScriptRoot\Collect-WindowsMetrics.ps1 `
        -RootProcessId $p.Id `
        -DurationSeconds $MeasureSeconds `
        -OutFile $metrics `
        -SkipGpu:$SkipGpu
    $after=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $summary=@{
        schema=3
        scenario=$Scenario
        app_exe=$AppExe
        root_pid=$p.Id
        warmup_seconds=$WarmupSeconds
        requested_measure_seconds=$MeasureSeconds
        elapsed_seconds=[math]::Round(((Get-Date)-$measureStarted).TotalSeconds,2)
        available_mib_before=[double]$before.AvailableMBytes
        available_mib_after=[double]$after.AvailableMBytes
        available_mib_delta=[math]::Round([double]$after.AvailableMBytes-[double]$before.AvailableMBytes,2)
        committed_mib_before=[math]::Round([double]$before.CommittedBytes/1MB,2)
        committed_mib_after=[math]::Round([double]$after.CommittedBytes/1MB,2)
        committed_mib_delta=[math]::Round([double]$after.CommittedBytes/1MB-[double]$before.CommittedBytes/1MB,2)
    }
    $summary | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $OutDir 'desktop-summary.json')
    & $Python $PSScriptRoot\Analyze-WindowsQualification.py $metrics `
        --scenario $Scenario `
        --desktop-summary (Join-Path $OutDir 'desktop-summary.json') `
        --json-out (Join-Path $OutDir 'qualification.json')
    if($LASTEXITCODE -ne 0){throw 'Qualification gates failed'}
}
finally {
    try {
        $p.CloseMainWindow() | Out-Null
        Start-Sleep 2
    } catch {}
    if(-not $p.HasExited){
        Stop-Process $p.Id -Force -ErrorAction SilentlyContinue
    }
}
