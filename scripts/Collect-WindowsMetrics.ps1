param(
    [Parameter(Mandatory=$true)][int]$RootProcessId,
    [int]$DurationSeconds=20,
    [int]$IntervalMilliseconds=1000,
    [string]$OutFile="metatron-windows-metrics.json",
    [switch]$SkipGpu,
    [ValidateRange(1,30)][int]$GpuCounterTimeoutSeconds=4,
    [ValidateRange(1,60)][int]$GpuPollIntervalSeconds=5
)

$ErrorActionPreference='Stop'
if($RootProcessId -le 0 -or $DurationSeconds -le 0 -or $IntervalMilliseconds -lt 100){
    throw 'Invalid process or sampling interval'
}


Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class MetatronGuiResources {
  [DllImport("kernel32.dll", SetLastError=true)] public static extern IntPtr OpenProcess(uint access, bool inherit, int pid);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetGuiResources(IntPtr hProcess, uint uiFlags);
}
"@ -ErrorAction SilentlyContinue

function Get-GuiResourceCounts([int]$ProcessId) {
    $PROCESS_QUERY_INFORMATION=0x0400
    $h=[MetatronGuiResources]::OpenProcess($PROCESS_QUERY_INFORMATION,$false,$ProcessId)
    if($h -eq [IntPtr]::Zero){return $null}
    try {
        [pscustomobject]@{
            gdi=[int][MetatronGuiResources]::GetGuiResources($h,0)
            user=[int][MetatronGuiResources]::GetGuiResources($h,1)
        }
    } finally { [MetatronGuiResources]::CloseHandle($h) | Out-Null }
}

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
    $visited=@{}
    $ids=@()
    while($queue.Count -gt 0) {
        $current=$queue.Dequeue()
        if($visited.ContainsKey($current)){continue}
        $visited[$current]=$true
        $ids+=$current
        if($map.ContainsKey($current)){
            foreach($childId in $map[$current]){$queue.Enqueue($childId)}
        }
    }
    return $ids
}

# Some WDDM/driver combinations can make Get-Counter stall. Isolate the call in
# a disposable job and disable GPU polling after the first timeout/failure.
# Missing GPU telemetry is reported as null, never zero.
function Get-BoundedGpuCounters([int]$TimeoutSeconds) {
    $job=Start-Job -ScriptBlock {
        $ErrorActionPreference='Stop'
        $shared=@(Get-Counter '\GPU Process Memory(*)\Shared Usage' -MaxSamples 1)
        $dedicated=@(Get-Counter '\GPU Process Memory(*)\Dedicated Usage' -MaxSamples 1)
        $engine=@(Get-Counter '\GPU Engine(*)\Utilization Percentage' -MaxSamples 1)
        [pscustomobject]@{
            shared=@($shared[0].CounterSamples)
            dedicated=@($dedicated[0].CounterSamples)
            engine=@($engine[0].CounterSamples)
        }
    }
    try {
        if(-not (Wait-Job -Job $job -Timeout $TimeoutSeconds)){
            throw "GPU counters exceeded $TimeoutSeconds seconds"
        }
        if($job.State -ne 'Completed'){throw 'GPU counter worker failed'}
        return Receive-Job -Job $job -ErrorAction Stop
    } finally {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
        Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
}

# Refuse vacuous success for a dead or reused root PID.
try {
    $rootStart=(Get-Process -Id $RootProcessId -ErrorAction Stop).StartTime.ToUniversalTime()
} catch {
    throw 'Root process is not running or cannot be inspected'
}

$logical=[int](Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
if($logical -lt 1){$logical=1}
$rows=@()
$count=[math]::Max(1,[int][math]::Ceiling(($DurationSeconds*1000)/$IntervalMilliseconds))
$gpuEnabled=-not $SkipGpu
$gpuFailure=if($SkipGpu){'Skipped by operator'}else{$null}
$lastGpuPollMs=0L
$cachedGpuShared=$null
$cachedGpuDedicated=$null
$cachedGpu3d=$null
$previousIds=@()

for($i=0;$i -lt $count;$i++) {
    $sampleStart=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    try {
        $currentRoot=Get-Process -Id $RootProcessId -ErrorAction Stop
        if($currentRoot.StartTime.ToUniversalTime() -ne $rootStart){throw 'Root PID was reused'}
    } catch {
        throw "Root process terminated or PID reused: $($_.Exception.Message)"
    }

    $ids=@(Get-ProcessTree $RootProcessId)
    if($ids.Count -lt 1){throw 'Process tree unexpectedly empty'}

    $perf=@(Get-CimInstance Win32_PerfFormattedData_PerfProc_Process -ErrorAction SilentlyContinue)
    $privateByPid=@{}
    foreach($entry in $perf){
        if($null -ne $entry.IDProcess -and $null -ne $entry.WorkingSetPrivate){
            $privateByPid[[int]$entry.IDProcess]=[long]$entry.WorkingSetPrivate
        }
    }

    $working=0L
    $privateBytes=0L
    $privateWorking=0L
    $cpu=0.0
    $handles=0L
    $threads=0L
    $gdiObjects=0L
    $userObjects=0L
    $readCount=0
    $privateWorkingCount=0
    $cpuCount=0
    $handleCount=0
    $threadCount=0
    $guiCount=0
    $processRows=@()

    foreach($id in $ids) {
        $name=$null
        $ws=$null
        $pb=$null
        $pws=$null
        $pcpu=$null
        $phandles=$null
        $pthreads=$null
        $pgdi=$null
        $puser=$null
        try {
            $p=Get-Process -Id $id -ErrorAction Stop
            $p.Refresh()
            $name=$p.ProcessName
            $ws=[long]$p.WorkingSet64
            $pb=[long]$p.PrivateMemorySize64
            $working+=$ws
            $privateBytes+=$pb
            $readCount++
            if($null -ne $p.CPU){
                $pcpu=[double]$p.CPU
                $cpu+=$pcpu
                $cpuCount++
            }
            try {
                $phandles=[int]$p.HandleCount
                $handles+=$phandles
                $handleCount++
            } catch {}
            try {
                $pthreads=[int]$p.Threads.Count
                $threads+=$pthreads
                $threadCount++
            } catch {}
            try {
                $gui=Get-GuiResourceCounts -ProcessId $id
                if($null -ne $gui){
                    $pgdi=[int]$gui.gdi
                    $puser=[int]$gui.user
                    $gdiObjects+=$pgdi
                    $userObjects+=$puser
                    $guiCount++
                }
            } catch {}
        } catch {}

        if($privateByPid.ContainsKey([int]$id)){
            $pws=[long]$privateByPid[[int]$id]
            $privateWorking+=$pws
            $privateWorkingCount++
        }

        $processRows += [pscustomobject]@{
            pid=[int]$id
            name=$name
            working_set_mib=$(if($null -ne $ws){[math]::Round($ws/1MB,2)}else{$null})
            private_bytes_mib=$(if($null -ne $pb){[math]::Round($pb/1MB,2)}else{$null})
            private_working_set_mib=$(if($null -ne $pws){[math]::Round($pws/1MB,2)}else{$null})
            cpu_seconds=$(if($null -ne $pcpu){[math]::Round($pcpu,3)}else{$null})
            handles=$phandles
            threads=$pthreads
            gdi_objects=$pgdi
            user_objects=$puser
        }
    }

    $mem=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
    $gpuShared=$cachedGpuShared
    $gpuDedicated=$cachedGpuDedicated
    $gpu3d=$cachedGpu3d
    $nowMs=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()

    if($gpuEnabled -and ($lastGpuPollMs -eq 0 -or ($nowMs-$lastGpuPollMs) -ge ($GpuPollIntervalSeconds*1000))) {
        try {
            $counters=Get-BoundedGpuCounters $GpuCounterTimeoutSeconds
            $shared=0.0
            $dedicated=0.0
            $engine=0.0
            foreach($id in $ids) {
                $pidRegex="pid_$id(?:_|$)"
                foreach($sample in @($counters.shared)){
                    if($sample.InstanceName -match $pidRegex){$shared+=[double]$sample.CookedValue}
                }
                foreach($sample in @($counters.dedicated)){
                    if($sample.InstanceName -match $pidRegex){$dedicated+=[double]$sample.CookedValue}
                }
                foreach($sample in @($counters.engine)){
                    if($sample.InstanceName -match $pidRegex -and $sample.InstanceName -match 'engtype_3D'){
                        $engine+=[double]$sample.CookedValue
                    }
                }
            }
            $cachedGpuShared=[math]::Round($shared/1MB,2)
            $cachedGpuDedicated=[math]::Round($dedicated/1MB,2)
            $cachedGpu3d=[math]::Round([math]::Min(100,$engine),2)
            $gpuShared=$cachedGpuShared
            $gpuDedicated=$cachedGpuDedicated
            $gpu3d=$cachedGpu3d
            $lastGpuPollMs=$nowMs
        } catch {
            $gpuFailure=$_.Exception.Message
            Write-Warning "GPU counter unavailable: $gpuFailure; remaining GPU readings will be null"
            $gpuEnabled=$false
            $cachedGpuShared=$null
            $cachedGpuDedicated=$null
            $cachedGpu3d=$null
            $gpuShared=$null
            $gpuDedicated=$null
            $gpu3d=$null
        }
    }

    if($i -eq 0){
        $added=@()
        $removed=@()
    } else {
        $added=@($ids | Where-Object {$_ -notin $previousIds})
        $removed=@($previousIds | Where-Object {$_ -notin $ids})
    }
    $previousIds=@($ids)

    $sampleEnd=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    $elapsed=$sampleEnd-$sampleStart
    $commitLimit=[double]$mem.CommitLimit/1MB
    $committed=[double]$mem.CommittedBytes/1MB
    $commitPct=if($commitLimit -gt 0){[math]::Round(($committed/$commitLimit)*100,2)}else{$null}

    $rows += [pscustomobject]@{
        ts=$sampleStart
        sample_elapsed_ms=$elapsed
        interval_overrun_ms=[math]::Max(0,$elapsed-$IntervalMilliseconds)
        process_count=$ids.Count
        process_ids=$ids
        process_added_pids=$added
        process_removed_pids=$removed
        process_details=$processRows
        working_set_mib=$(if($readCount -eq $ids.Count){[math]::Round($working/1MB,2)}else{$null})
        private_working_set_mib=$(if($privateWorkingCount -eq $ids.Count){[math]::Round($privateWorking/1MB,2)}else{$null})
        private_bytes_mib=$(if($readCount -eq $ids.Count){[math]::Round($privateBytes/1MB,2)}else{$null})
        process_cpu_seconds=$(if($cpuCount -eq $ids.Count){[math]::Round($cpu,3)}else{$null})
        handle_count=$(if($handleCount -eq $ids.Count){$handles}else{$null})
        thread_count=$(if($threadCount -eq $ids.Count){$threads}else{$null})
        gdi_object_count=$(if($guiCount -eq $ids.Count){$gdiObjects}else{$null})
        user_object_count=$(if($guiCount -eq $ids.Count){$userObjects}else{$null})
        memory_coverage=$readCount
        private_working_set_coverage=$privateWorkingCount
        cpu_coverage=$cpuCount
        handle_coverage=$handleCount
        thread_coverage=$threadCount
        gui_resource_coverage=$guiCount
        logical_processors=$logical
        system_available_mib=[double]$mem.AvailableMBytes
        system_committed_mib=[math]::Round($committed,2)
        system_commit_limit_mib=[math]::Round($commitLimit,2)
        system_commit_percent=$commitPct
        gpu_shared_mib=$gpuShared
        gpu_dedicated_mib=$gpuDedicated
        gpu_3d_percent=$gpu3d
    }

    $sleep=[math]::Max(0,$IntervalMilliseconds-$elapsed)
    if($sleep -gt 0){Start-Sleep -Milliseconds $sleep}
}

$report=@{
    schema=5
    root_pid=$RootProcessId
    root_start_utc=$rootStart.ToString('o')
    duration_seconds=$DurationSeconds
    interval_ms=$IntervalMilliseconds
    gpu_poll_interval_seconds=$GpuPollIntervalSeconds
    gpu_counter_error=$gpuFailure
    samples=$rows
}
$report | ConvertTo-Json -Depth 9 | Set-Content -Encoding UTF8 $OutFile
