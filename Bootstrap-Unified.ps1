[CmdletBinding()]
param(
    [string]$WorkDir = (Join-Path $env:USERPROFILE "Projects\Unified-NPU-Jarvis"),
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$EzCommit = "5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a"
$OdCommit = "0cc8c643e82661295b674d3de90daa8e5524e27b"

function Need($cmd, $wingetId) {
    if (Get-Command $cmd -ErrorAction SilentlyContinue) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$cmd is missing and winget is unavailable"
    }
    winget install --id $wingetId -e --accept-package-agreements --accept-source-agreements
}

Need git "Git.Git"

New-Item -ItemType Directory -Force -Path $WorkDir | Out-Null
$Ez = Join-Path $WorkDir "EZSTT"
$Od = Join-Path $WorkDir "OpenDex-reference"

if (-not (Test-Path (Join-Path $Ez ".git"))) {
    git clone https://github.com/aurickk/EZSTT.git $Ez
}
git -C $Ez fetch origin
git -C $Ez checkout $EzCommit

if (-not (Test-Path (Join-Path $Od ".git"))) {
    git clone https://github.com/aviarytech/jarvis.git $Od
}
git -C $Od fetch origin
git -C $Od checkout $OdCommit

Push-Location $Ez
try {
    $branch = "unified-npu-jarvis"
    if (git branch --list $branch) {
        git checkout $branch
    } else {
        git checkout -b $branch
    }
} finally {
    Pop-Location
}

$Apply = Join-Path $PSScriptRoot "Apply-JarvisLite.ps1"
& $Apply -EzsttPath $Ez

$Notice = Join-Path $PSScriptRoot "THIRD_PARTY_NOTICES.md"
Copy-Item $Notice (Join-Path $Ez "THIRD_PARTY_NOTICES.md") -Force

$AgentBridge = Join-Path $PSScriptRoot "patch_payload\engine\ezstt\agent_bridge.py"
Copy-Item $AgentBridge (Join-Path $Ez "engine\ezstt\agent_bridge.py") -Force

Write-Host "`nUnified source workspace prepared." -ForegroundColor Green
Write-Host "EZSTT working tree: $Ez"
Write-Host "OpenDex reference:   $Od"
Write-Host ""
Write-Host "Next: give AGENT_MERGE_PROMPT.md to the local coding agent."

if (-not $SkipBuild) {
    Write-Host "`nAttempting frontend build..." -ForegroundColor Cyan
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Push-Location $Ez
        try {
            npm install
            npm run build
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "npm not found; local agent must install Node.js and build."
    }
}
