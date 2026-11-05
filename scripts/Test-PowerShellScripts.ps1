param([string]$Python='python')
$ErrorActionPreference='Stop';$Root=Split-Path -Parent $PSScriptRoot;$errors=@()
Get-ChildItem $PSScriptRoot -Filter '*.ps1' | ForEach-Object {$tokens=$null;$parseErrors=$null;[void][System.Management.Automation.Language.Parser]::ParseFile($_.FullName,[ref]$tokens,[ref]$parseErrors);if($parseErrors.Count){$errors += $parseErrors}}
if($errors.Count){$errors|ForEach-Object{Write-Error $_};exit 2}
$p=Start-Process $env:ComSpec -ArgumentList '/c','ping -t 127.0.0.1' -PassThru -WindowStyle Hidden
try{$out=Join-Path $env:TEMP ('metatron-metrics-'+[guid]::NewGuid().ToString('N')+'.json');& $PSScriptRoot\Collect-WindowsMetrics.ps1 -RootProcessId $p.Id -DurationSeconds 2 -IntervalMilliseconds 500 -OutFile $out -SkipGpu;$j=Get-Content $out -Raw|ConvertFrom-Json;if($j.samples.Count -lt 2){throw 'metrics smoke returned too few samples'};Remove-Item $out -Force -EA SilentlyContinue}finally{Stop-Process $p.Id -Force -EA SilentlyContinue}
Write-Host 'PowerShell parse + metrics smoke PASS'
