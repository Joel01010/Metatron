[CmdletBinding()]
param(
    [string]$Python = "py",
    [string]$Venv = ".venv-orukeet"
)

$ErrorActionPreference = "Stop"

Write-Host "Setting up isolated Orukeet NPU lab..." -ForegroundColor Cyan

if (-not (Test-Path $Venv)) {
    try {
        & $Python -3.12 -m venv $Venv
    } catch {
        python -m venv $Venv
    }
}

$Py = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Virtual environment Python not found."
}

& $Py -m pip install --upgrade pip
& $Py -m pip install "openvino==2026.4.0" "huggingface_hub>=0.34,<2"

Write-Host "`nDownloading verified Orukeet INT8 ONNX export..." -ForegroundColor Cyan
& $Py (Join-Path $PSScriptRoot "download_orukeet_onnx.py") `
    --out (Join-Path $PSScriptRoot "orukeet-model") `
    --cache (Join-Path $PSScriptRoot "orukeet-cache")

Write-Host "`nProbing direct OpenVINO NPU compilation..." -ForegroundColor Cyan
& $Py (Join-Path $PSScriptRoot "probe_orukeet_npu.py") `
    --model-dir (Join-Path $PSScriptRoot "orukeet-model") `
    --cache-dir (Join-Path $PSScriptRoot "orukeet-npu-cache")

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nOrukeet passed the NPU compile gate." -ForegroundColor Green
    Write-Host "Next: integrate encoder NPU + decoder/joiner CPU and benchmark real dictation."
} else {
    Write-Warning "Orukeet did not pass the direct NPU compile gate yet."
    Write-Warning "Do NOT replace Parakeet Unified. Let the coding agent adapt static shapes/export."
}
