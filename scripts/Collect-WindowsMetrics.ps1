param(
    [Parameter(Mandatory=$true)][int]$RootProcessId,
    [int]$DurationSeconds=20,
    [int]$IntervalMilliseconds=1000,
    [string]$OutFile="metatron-windows-metrics.json",
    [switch]$SkipGpu,
    [ValidateRange(1,30)][int]$GpuCounterTimeoutSeconds=4
)
$ErrorActionPreference='Stop'
if($RootProcessId -le 0 -or $DurationSeconds -le 0 -or $IntervalMilliseconds -lt 100){throw 'Invalid process or sampling interval'}

function Get-ProcessTree([int]$RootId) {
    $all=@(Get-CimInstance Win32_Process)
    $map=@{}
    foreach($process in $all) {
        $parent=[int]$process.ParentProcessId
        if(-not $map.ContainsKey($parent)){$map[$parent]=@()}
        $map[$parent]+=[int]$process.ProcessId
    }
    $queue=New-Object 'System.Collections.Generic.Queue[int]'
    $queue.Enqueue($RootId)
    $visited=@{}; $ids=@()
    while($queue.Count -gt 0) {
        $current=$queue.Dequeue()
        if($visited.ContainsKey($current)){continue}
        $visited[$current]=$true
        $ids+= $current
        if($map.ContainsKey($current)){foreach($childId in $map[$current]){$queue.Enqueue($childId)}}
    }
    return $ids
}

# Get-Counter can hang in damaged drivers or on WDDM machines with unavailable counters.
# Isolate it in a disposable PowerShell job, then permanently disable GPU polling for
# this qualification if its first attempt times out or fails. Missing is NOT zero.
function Get-BoundedGpuCounters([int]$TimeoutSeconds) {
    $job=Start-Job -ScriptBlock {
        $ErrorActionPreference='Stop'
        $shared=@(Get-Counter '\GPU Process Memory(*)\Shared Usage' -MaxSamples 1)
        $dedicated=@(Get-Counter '\GPU Process Memory(*)\Dedicated Usage' -MaxSamples 1)
        $engine=@(Get-Counter '\GPU Engine(*)\Utilization Percentage' -MaxSamples 1)
        [pscustomobject]@{shared=@($shared[0].CounterSamples);dedicated=@($dedicated[0].CounterSamples);engine=@($engine[0].CounterSamples)}
    }
    try {
        if(-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)) {throw "GPU counters exceeded $TimeoutSeconds seconds"}
        if($job.State -ne 'Completed'){throw 'GPU counter worker failed'}
        return Receive-Job -Job $job -ErrorAction Stop
    } finally {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Refuse vacuous success for a dead or reused root PID.
try {$rootStart=(Get-Process -Id $RootProcessId -ErrorAction Stop).StartTime.ToUniversalTime()} catch {throw 'Root process is not running or cannot be inspected'}
$logical=[int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
if($logical -lt 1){$logical=1}
$rows=@()
$count=[math]::Max(1,[int][math]::Ceiling(($DurationSeconds*1000)/$IntervalMilliseconds))
$gpuEnabled= -not $SkipGpu
$gpuFailure= if($SkipGpu){'Skipped by operator'}else{$null}
for($i=0;$i -lt $count;$i++) {
    $sampleStart=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    try {
        $currentRoot=Get-Process -Id $RootProcessId -ErrorAction Stop
        if($currentRoot.StartTime.ToUniversalTime() -ne $rootStart) {throw 'Root PID was reused'}
    } catch {throw "Root process terminated or PID reused: $($_.Exception.Message)"}
    $ids=@(Get-ProcessTree $RootProcessId)
    $working=0L; $privateBytes=0L; $privateWorking=0L; $cpu=0.0
    $readCount=0; $privateWorkingCount=0; $cpuCount=0
    $perf=@(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -ErrorAction SilentlyContinue)
    foreach($id in $ids) {
        try {
            $p=Get-Process -Id $id -ErrorAction Stop
            $working+=$p.WorkingSet64
            $privateBytes+=$p.PrivateMemorySize64
            $readCount++
            if($null -ne $p.CPU){$cpu+=[double]$p.CPU; $cpuCount++}
        } catch {}
        $match=@($perf | Where-Object {[int]$_.IDProcess -eq $id} | Select-Object -First 1)
        if($match.Count -gt 0 -and $null -ne $match[0].WorkingSetPrivate){
            $privateWorking+=[long]$match[0].WorkingSetPrivate
            $privateWorkingCount++
        }
    }
    $mem=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $gpuShared=$null; $gpuDedicated=$null; $gpu3d=$null
    if($gpuEnabled) {
        try {
            $counters=Get-BoundedGpuCounters $GpuCounterTimeoutSeconds
            $shared=0.0; $dedicated=0.0; $engine=0.0
            foreach($id in $ids) {
                $pidRegex="pid_$id(?:_|$)"
                foreach($sample in @($counters.shared)) {if($sample.InstanceName -match $pidRegex){$shared+=[double]$sample.CookedValue}}
                foreach($sample in @($counters.dedicated)) {if($sample.InstanceName -match $pidRegex){$dedicated+=[double]$sample.CookedValue}}
                foreach($sample in @($counters.engine)) {if($sample.InstanceName -match $pidRegex -and $sample.InstanceName -match 'engtype_3D'){$engine+=[double]$sample.CookedValue}}
            }
            $gpuShared=[math]::Round($shared/1MB,2)
            $gpuDedicated=[math]::Round($dedicated/1MB,2)
            $gpu3d=[math]::Round([math]::Min(100,$engine),2)
        } catch {
            $gpuFailure=$_.Exception.Message
            Write-Warning "GPU counter unavailable: $gpuFailure; remaining GPU readings will be null"
            $gpuEnabled=$false
        }
    }
    $rows += [pscustomobject]@{
        ts=$sampleStart;process_count=$ids.Count;process_ids=$ids
        working_set_mib=$(if($readCount -eq $ids.Count){[math]::Round($working/1MB,2)}else{$null})
        private_working_set_mib=$(if($privateWorkingCount -eq $ids.Count){[math]::Round($privateWorking/1MB,2)}else{$null})
        private_bytes_mib=$(if($readCount -eq $ids.Count){[math]::Round($privateBytes/1MB,2)}else{$null})
        process_cpu_seconds=$(if($cpuCount -eq $ids.Count){[math]::Round($cpu,3)}else{$null})
        memory_coverage=$readCount
        private_working_set_coverage=$privateWorkingCount
        logical_processors=$logical
        system_available_mib=[double]$mem.AvailableMBytes
        system_committed_mib=[math]::Round([double]$mem.CommittedBytes/1MB,2)
        system_commit_limit_mib=[math]::Round([double]$mem.CommitLimit/1MB,2)
        gpu_shared_mib=$gpuShared;gpu_dedicated_mib=$gpuDedicated;gpu_3d_percent=$gpu3d
    }
    $elapsed=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()-$sampleStart
    $sleep=[math]::Max(0,$IntervalMilliseconds-$elapsed)
    if($sleep -gt 0){Start-Sleep -Milliseconds $sleep}
}
$report=@{schema=3;root_pid=$RootProcessId;root_start_utc=$rootStart.ToString('o');duration_seconds=$DurationSeconds;interval_ms=$IntervalMilliseconds;gpu_counter_error=$gpuFailure;samples=$rows}
$report|ConvertTo-Json -Depth 7|Set-Content -Encoding UTF8 $OutFile
