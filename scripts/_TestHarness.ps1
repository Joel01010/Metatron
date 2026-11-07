# Shared helpers for Metatron's local Windows qualification scripts.
# PowerShell 5.1 compatible by design.
Set-StrictMode -Version 2.0

function Write-TestStage {
    param([Parameter(Mandatory=$true)][string]$Name)
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor DarkGray
    Write-Host ("METATRON TEST STAGE: {0}" -f $Name) -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor DarkGray
}

function Ensure-TestDirectory {
    param([Parameter(Mandatory=$true)][string]$Path)
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    return [IO.Path]::GetFullPath($Path)
}

function Refresh-ProcessPath {
    $machine=[Environment]::GetEnvironmentVariable('Path','Machine')
    $user=[Environment]::GetEnvironmentVariable('Path','User')
    $extra=@(
        (Join-Path $env:USERPROFILE '.cargo\bin'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\Scripts')
    ) | Where-Object { $_ -and (Test-Path $_) }
    $parts=@($machine,$user)+@($extra)
    $env:Path=(@($parts | Where-Object {$_}) -join ';')
}

function Invoke-TestNative {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [string[]]$ArgumentList=@(),
        [Parameter(Mandatory=$true)][string]$Label,
        [string]$LogPath='',
        [switch]$AllowFailure
    )
    if($LogPath){
        $parent=Split-Path -Parent $LogPath
        if($parent){New-Item -ItemType Directory -Force -Path $parent | Out-Null}
    }
    $old=$ErrorActionPreference
    $code=1
    try {
        # Windows PowerShell 5.1 may wrap native stderr as ErrorRecord under Stop.
        # Native exit code is authoritative for git/npm/pip/cargo/python.
        $ErrorActionPreference='Continue'
        if($LogPath){
            & $FilePath @ArgumentList 2>&1 | Tee-Object -FilePath $LogPath | Out-Host
        } else {
            & $FilePath @ArgumentList
        }
        $code=$LASTEXITCODE
        if($null -eq $code){$code=0}
    } finally {
        $ErrorActionPreference=$old
    }
    if($code -ne 0 -and -not $AllowFailure){
        throw "$Label failed with exit $code"
    }
    return [int]$code
}

function Get-PythonExecutable {
    param([string]$Requested='auto')
    $candidates=New-Object System.Collections.ArrayList
    if($Requested -and $Requested -ne 'auto'){
        [void]$candidates.Add($Requested)
    }
    foreach($name in @('python','python3')){
        $cmd=Get-Command $name -ErrorAction SilentlyContinue
        if($cmd){[void]$candidates.Add($cmd.Source)}
    }
    $py=Get-Command py -ErrorAction SilentlyContinue
    if($py){
        foreach($selector in @('-3.12','-3.11')){
            $old=$ErrorActionPreference
            try {
                $ErrorActionPreference='Continue'
                $resolved=& $py.Source $selector -c 'import sys; print(sys.executable)' 2>$null
                $code=$LASTEXITCODE
            } finally {$ErrorActionPreference=$old}
            if($code -eq 0 -and $resolved){[void]$candidates.Add(([string]$resolved).Trim())}
        }
    }
    $seen=@{}
    foreach($candidate in $candidates){
        if(-not $candidate){continue}
        $key=[string]$candidate
        if($seen.ContainsKey($key)){continue}
        $seen[$key]=$true
        try {
            $old=$ErrorActionPreference
            try {
                $ErrorActionPreference='Continue'
                $info=& $candidate -c 'import json,sys; print(json.dumps({"exe":sys.executable,"major":sys.version_info.major,"minor":sys.version_info.minor}))' 2>$null
                $code=$LASTEXITCODE
            } finally {$ErrorActionPreference=$old}
            if($code -ne 0 -or -not $info){continue}
            $obj=([string]$info | Select-Object -Last 1 | ConvertFrom-Json)
            if([int]$obj.major -eq 3 -and [int]$obj.minor -ge 11){
                return [string]$obj.exe
            }
        } catch {}
    }
    return ''
}

function Read-JsonFileSafe {
    param([string]$Path)
    if(-not $Path -or -not (Test-Path $Path)){return $null}
    try{return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)}catch{return $null}
}

function Write-TestSummary {
    param(
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$Name,
        [Parameter(Mandatory=$true)][string]$Status,
        [object[]]$Results=@(),
        [hashtable]$Extra=@{}
    )
    $obj=[ordered]@{
        schema=1
        suite=$Name
        status=$Status
        generated_at=(Get-Date).ToUniversalTime().ToString('o')
        results=$Results
    }
    foreach($k in $Extra.Keys){$obj[$k]=$Extra[$k]}
    $obj | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}
