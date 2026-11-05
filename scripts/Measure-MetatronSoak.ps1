param(
    [string]$AppExe="",
    [int]$DurationMinutes=30,
    [int]$WarmupSeconds=30,
    [int]$IntervalSeconds=5,
    [string]$Python="python",
    [string]$OutDir="",
    [switch]$SkipGpu,
    [double]$MaxGrowthMiBPerHour=64,
    [double]$MaxQuartileDeltaMiB=128,
    [double]$MaxPrivateWsMiB=2560,
    [double]$MaxPrivateBytesMiB=3072,
    [double]$MaxPrivateBytesGrowthMiBPerHour=64,
    [double]$MaxPrivateBytesQuartileDeltaMiB=128,
    [double]$MinCompleteRatio=0.95
)

$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
if(-not $OutDir){$OutDir=Join-Path $Root ('build\soak-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Force $OutDir | Out-Null
if(-not $AppExe){
    $AppExe=@(
        (Join-Path $Root 'src-tauri\target\release\metatron.exe'),
        (Join-Path $Root 'src-tauri\target\release\Metatron.exe')
    ) | Where-Object {Test-Path $_} | Select-Object -First 1
}
if(-not $AppExe){throw 'Built Metatron executable not found'}
if($DurationMinutes -lt 1){throw 'DurationMinutes must be at least 1'}
if($IntervalSeconds -lt 1){throw 'IntervalSeconds must be at least 1'}

$p=Start-Process $AppExe -PassThru
try {
    Start-Sleep $WarmupSeconds
    if($p.HasExited){throw "Metatron exited during soak warm-up: $($p.ExitCode)"}
    $metrics=Join-Path $OutDir 'soak-metrics.json'
    & $PSScriptRoot\Collect-WindowsMetrics.ps1 `
        -RootProcessId $p.Id `
        -DurationSeconds ($DurationMinutes*60) `
        -IntervalMilliseconds ($IntervalSeconds*1000) `
        -OutFile $metrics `
        -SkipGpu:$SkipGpu
    & $Python $PSScriptRoot\Analyze-Soak.py $metrics `
        --max-growth-mib-per-hour $MaxGrowthMiBPerHour `
        --max-quartile-delta-mib $MaxQuartileDeltaMiB `
        --max-private-ws-mib $MaxPrivateWsMiB `
        --max-private-bytes-mib $MaxPrivateBytesMiB `
        --max-private-bytes-growth-mib-per-hour $MaxPrivateBytesGrowthMiBPerHour `
        --max-private-bytes-quartile-delta-mib $MaxPrivateBytesQuartileDeltaMiB `
        --min-complete-ratio $MinCompleteRatio `
        --json-out (Join-Path $OutDir 'soak-analysis.json')
    if($LASTEXITCODE -ne 0){throw 'Soak/leak gate failed'}
}
finally {
    try {
        $p.CloseMainWindow() | Out-Null
        Start-Sleep 2
    } catch {}
    if(-not $p.HasExited){Stop-Process $p.Id -Force -ErrorAction SilentlyContinue}
}
