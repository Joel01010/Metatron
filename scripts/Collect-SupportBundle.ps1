param([string]$OutFile="",[switch]$IncludeLogs,[string]$Python="python")
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
if(-not $OutFile){$OutFile=Join-Path $Root "Metatron-Support-$stamp.zip"}
$tmp=Join-Path ([IO.Path]::GetTempPath()) "metatron-support-$stamp"
New-Item -ItemType Directory -Force $tmp|Out-Null
try{
    @{
        generated_at=(Get-Date).ToUniversalTime().ToString('o')
        os=(Get-CimInstance Win32_OperatingSystem|Select-Object Caption,Version,BuildNumber,OSArchitecture)
        computer=(Get-CimInstance Win32_ComputerSystem|Select-Object Manufacturer,Model,TotalPhysicalMemory)
        cpu=(Get-CimInstance Win32_Processor|Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
        display=(Get-CimInstance Win32_VideoController|Select-Object Name,DriverVersion,AdapterRAM)
        npu=(Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue|Where-Object {$_.FriendlyName-match'NPU|Neural|AI Boost|Hexagon|Ryzen AI'}|Select-Object FriendlyName,Class,Status,InstanceId)
    }|ConvertTo-Json -Depth 6|Set-Content -Encoding UTF8 (Join-Path $tmp 'system.json')
    & $Python $PSScriptRoot\product_audit.py --json-out (Join-Path $tmp 'product-audit.json')|Out-Null
    & $Python $PSScriptRoot\Verify-Accelerators.py --report (Join-Path $tmp 'accelerators.json')|Out-Null
    $speechManifest=if($env:LOCALAPPDATA){Join-Path $env:LOCALAPPDATA 'Metatron\runtimes\speech-command.json'}else{''}
    if($env:METATRON_SPEECH_CMD -or ($speechManifest -and (Test-Path $speechManifest))){
        & $Python $PSScriptRoot\Verify-SpeechRuntime.py --json-out (Join-Path $tmp 'speech.json')|Out-Null
    }
    if($IncludeLogs){
        $build=Join-Path $Root 'build'
        if(Test-Path $build){
            Get-ChildItem $build -Recurse -File -Include *.log,*.json -ErrorAction SilentlyContinue | Select-Object -First 200 | ForEach-Object {
                Copy-Item $_.FullName (Join-Path $tmp ('log-'+$_.Name)) -Force -ErrorAction SilentlyContinue
            }
        }
    }
    @{note='Excludes secrets, SQLite database, transcript history and audio.'}|ConvertTo-Json|Set-Content -Encoding UTF8 (Join-Path $tmp 'privacy-note.json')
    Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath $OutFile -Force
}finally{Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue}
Write-Host "Support bundle: $OutFile"
