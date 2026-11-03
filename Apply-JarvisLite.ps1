[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$EzsttPath
)

$ErrorActionPreference = "Stop"

$ExpectedCommit = "5f31cfb19e20a4a723a39be8f4e2d22d3290fb3a"

if (-not (Test-Path (Join-Path $EzsttPath ".git"))) {
    throw "Not an EZSTT git checkout: $EzsttPath"
}

$head = (git -C $EzsttPath rev-parse HEAD).Trim()
if ($head -ne $ExpectedCommit) {
    Write-Warning "Expected EZSTT base $ExpectedCommit but checkout is $head."
    Write-Warning "The payload files can still be copied, but review overlay.rs manually."
}

$payload = Join-Path $PSScriptRoot "patch_payload"

# Back up originals once.
$backup = Join-Path $EzsttPath ".unified-backup"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
foreach ($rel in @(
    "ui\overlay.html",
    "ui\src\overlay.ts",
    "ui\src\overlay.css"
)) {
    $src = Join-Path $EzsttPath $rel
    if (Test-Path $src) {
        $dst = Join-Path $backup ($rel -replace '\\','__')
        if (-not (Test-Path $dst)) {
            Copy-Item $src $dst
        }
    }
}

Copy-Item (Join-Path $payload "ui\overlay.html") (Join-Path $EzsttPath "ui\overlay.html") -Force
Copy-Item (Join-Path $payload "ui\src\overlay.ts") (Join-Path $EzsttPath "ui\src\overlay.ts") -Force
Copy-Item (Join-Path $payload "ui\src\overlay.css") (Join-Path $EzsttPath "ui\src\overlay.css") -Force
Copy-Item (Join-Path $payload "ui\src\jarvis-lite.ts") (Join-Path $EzsttPath "ui\src\jarvis-lite.ts") -Force
Copy-Item (Join-Path $payload "ui\src\jarvis-lite.css") (Join-Path $EzsttPath "ui\src\jarvis-lite.css") -Force

# The original overlay window is only 360x72. Jarvis Lite needs a modestly larger
# transparent surface, but still far smaller than a full-screen permanent HUD.
$overlayRs = Join-Path $EzsttPath "src-tauri\src\overlay.rs"
if (Test-Path $overlayRs) {
    $s = Get-Content $overlayRs -Raw
    $oldW = "pub const WIDTH: f64 = 360.0;"
    $oldH = "pub const HEIGHT: f64 = 72.0;"
    if ($s.Contains($oldW)) { $s = $s.Replace($oldW, "pub const WIDTH: f64 = 520.0;") }
    if ($s.Contains($oldH)) { $s = $s.Replace($oldH, "pub const HEIGHT: f64 = 160.0;") }
    Set-Content -Encoding UTF8 $overlayRs $s
}

Write-Host "JARVIS Lite payload applied." -ForegroundColor Green
Write-Host "Original overlay files are backed up under .unified-backup."
