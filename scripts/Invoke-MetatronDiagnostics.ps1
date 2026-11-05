<#
Local Windows diagnostics entrypoint. Read-only, opt-in sampling. No installers or uploads.
Examples:
  .\scripts\Invoke-MetatronDiagnostics.ps1 -Python Z:\Metatron\.venv\Scripts\python.exe
  .\scripts\Invoke-MetatronDiagnostics.ps1 -Python Z:\Metatron\.venv\Scripts\python.exe -ProcessId 1234 -Seconds 120
  .\scripts\Invoke-MetatronDiagnostics.ps1 -Python Z:\Metatron\.venv\Scripts\python.exe -ProcessId 1234 -Seconds 60 -SkipGpu
#>
[CmdletBinding()]
param(
    [string]$Python='python',
    [string]$OutDir='',
    [int]$ProcessId=0,
    [ValidateRange(2,86400)][int]$Seconds=60,
    [ValidateRange(200,60000)][int]$IntervalMilliseconds=1000,
    [switch]$SkipGpu,
    [switch]$SkipTests,
    [switch]$SkipBenchmark,
    [switch]$WithCargo,
    [switch]$Bundle,
    [switch]$IncludeEventSummaries
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
if(-not $OutDir){$OutDir=Join-Path $Root ('build\diagnostics-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))}
New-Item -ItemType Directory -Path $OutDir -Force|Out-Null
$OutDir=(Resolve-Path $OutDir).Path
$sys=Get-CimInstance Win32_OperatingSystem
$cpu=Get-CimInstance Win32_Processor | Select-Object -First 1
$gpu=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,VideoProcessor)
$ram=Get-CimInstance Win32_ComputerSystem
$osinfo=[ordered]@{
    schema=1;captured_utc=[DateTime]::UtcNow.ToString('o');os_caption=$sys.Caption
    os_build=$sys.BuildNumber;os_version=$sys.Version
    cpu_name=$cpu.Name;logical_processors=$cpu.NumberOfLogicalProcessors
    installed_ram_mib=[math]::Round($ram.TotalPhysicalMemory/1MB,1)
    gpu=$gpu
    note='No usernames, installed software inventory, environment variables, or hardware serial numbers collected.'
}
$osinfo|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 (Join-Path $OutDir 'windows-inventory.json')
$runArgs=@('scripts/diagnostics/run_diagnostics.py','--out',$OutDir)
if($SkipTests){$runArgs+='--skip-tests'}
if($SkipBenchmark){$runArgs+='--skip-benchmark'}
if($WithCargo){$runArgs+='--with-cargo'}
if($ProcessId -gt 0){$runArgs+=@('--pid',"$ProcessId",'--sample-seconds',"$Seconds")}
# Record exit without losing output; native stderr is often informational.
$oldPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & $Python @runArgs 2>&1 | Tee-Object -FilePath (Join-Path $OutDir 'portable-run.log')
    $portableExit=$LASTEXITCODE
} finally {$ErrorActionPreference=$oldPreference}
if($ProcessId -gt 0){
    $native=Join-Path $OutDir 'windows-metrics.json'
    try {
        & (Join-Path $PSScriptRoot 'Collect-WindowsMetrics.ps1') -RootProcessId $ProcessId -DurationSeconds $Seconds -IntervalMilliseconds $IntervalMilliseconds -OutFile $native -SkipGpu:$SkipGpu
        if(-not (Test-Path $native)){throw 'Windows native collection produced no output'}
        & $Python (Join-Path $PSScriptRoot 'diagnostics/analyze_telemetry.py') $native --out (Join-Path $OutDir 'windows-metrics-analysis.json')
        if($LASTEXITCODE -ne 0){throw 'Native metrics analysis did not complete'}
    }catch{
        @{status='FAIL';reason=$_.Exception.Message}|ConvertTo-Json|Set-Content -Encoding UTF8 (Join-Path $OutDir 'windows-metrics-error.json')
        Write-Warning "Native metrics failed: $($_.Exception.Message)"
    }
}
if($IncludeEventSummaries){
    # Only counts and timestamps. Event messages may contain private paths, so never collect messages.
    try {
        $cutoff=(Get-Date).AddHours(-24)
        $items=@(Get-WinEvent -FilterHashtable @{LogName='Application';StartTime=$cutoff;Level=2} -MaxEvents 100 -ErrorAction Stop |
            Where-Object {$_.ProviderName -match 'Application Error|Windows Error Reporting|\.NET Runtime'} |
            Select-Object TimeCreated,Id,ProviderName,LevelDisplayName)
        $items|ConvertTo-Json -Depth 3|Set-Content -Encoding UTF8 (Join-Path $OutDir 'recent-crash-event-summaries.json')
    }catch{Write-Warning "Event summary unavailable: $($_.Exception.Message)"}
}
# Shareable bundle excludes raw stdout/stderr and arbitrary logs: those might contain paths.
if($Bundle){
    $allow=@('windows-inventory.json','environment.json','diagnostic-summary.json','product-audit.json',
             'core-benchmark.json','process-analysis.json','windows-metrics-analysis.json',
             'windows-metrics-error.json','recent-crash-event-summaries.json')
    $safeDir=Join-Path $OutDir 'redacted-bundle'
    New-Item -ItemType Directory -Force $safeDir|Out-Null
    foreach($name in $allow){$p=Join-Path $OutDir $name;if(Test-Path $p){Copy-Item $p (Join-Path $safeDir $name)}}
    Compress-Archive -Path (Join-Path $safeDir '*') -DestinationPath (Join-Path $OutDir 'Metatron-Diagnostics-Redacted.zip') -Force
}
Write-Host "Diagnostic artifacts: $OutDir"
if($portableExit -ne 0){exit 2}
if(Test-Path (Join-Path $OutDir 'windows-metrics-error.json')){exit 2}
