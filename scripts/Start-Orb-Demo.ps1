param(
    [int]$Port = 8765,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Orb = $Root
Write-Host "Metatron orb demo: http://127.0.0.1:$Port/renderer/orb/" -ForegroundColor Cyan
Write-Host "Click = user speech; Shift+Click = AI speech" -ForegroundColor DarkGray
& $Python -m http.server $Port --bind 127.0.0.1 --directory $Orb
