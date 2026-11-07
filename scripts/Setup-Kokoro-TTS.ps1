param(
    [string]$Root = "",
    [string]$Python = "python",
    [ValidateSet("fp16", "int8", "fp32")]
    [string]$Precision = "fp16"
)
$ErrorActionPreference = "Stop"

function Invoke-NativeChecked {
    param([Parameter(Mandatory=$true)][string]$FilePath,[string[]]$ArgumentList=@(),[string]$Label='native command')
    $oldEap=$ErrorActionPreference; $code=1
    try { $ErrorActionPreference='Continue'; & $FilePath @ArgumentList; $code=$LASTEXITCODE }
    finally { $ErrorActionPreference=$oldEap }
    if($code -ne 0){throw "$Label failed with exit $code"}
}

if (-not $Root) { $Root = Join-Path $env:LOCALAPPDATA "Metatron" }
$Venv = Join-Path $Root "venvs\kokoro-tts"
$Models = Join-Path $Root "models\kokoro"
New-Item -ItemType Directory -Force -Path $Venv, $Models | Out-Null
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Invoke-NativeChecked -FilePath $Python -ArgumentList @('-m','venv',$Venv) -Label 'Kokoro venv creation'
}
$Py = Join-Path $Venv "Scripts\python.exe"
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','--upgrade','pip') -Label 'Kokoro pip upgrade'
Invoke-NativeChecked -FilePath $Py -ArgumentList @('-m','pip','install','kokoro-onnx>=0.6.0','soundfile') -Label 'Kokoro dependency install'

switch ($Precision) {
    "fp16" { $ModelName = "kokoro-v1.0.fp16.onnx"; $ExpectedApproxMB = 164 }
    "int8" { $ModelName = "kokoro-v1.0.int8.onnx"; $ExpectedApproxMB = 114 }
    default { $ModelName = "kokoro-v1.0.onnx"; $ExpectedApproxMB = 326 }
}
$Release = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
$Model = Join-Path $Models $ModelName
$Voices = Join-Path $Models "voices-v1.0.bin"
if (-not (Test-Path $Model)) {
    Write-Host "Downloading Kokoro $Precision model (~$ExpectedApproxMB MB)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "$Release/$ModelName" -OutFile $Model
}
if (-not (Test-Path $Voices)) { Invoke-WebRequest -Uri "$Release/voices-v1.0.bin" -OutFile $Voices }

$Manifest = @{
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
    precision = $Precision
    model = $Model
    model_sha256 = (Get-FileHash -LiteralPath $Model -Algorithm SHA256).Hash
    voices = $Voices
    voices_sha256 = (Get-FileHash -LiteralPath $Voices -Algorithm SHA256).Hash
} | ConvertTo-Json
$Manifest | Set-Content -LiteralPath (Join-Path $Models "install-manifest.json") -Encoding UTF8

$env:METATRON_KOKORO_PYTHON = $Py
$env:METATRON_KOKORO_MODEL = $Model
$env:METATRON_KOKORO_VOICES = $Voices
$env:METATRON_TTS_VOICE = "am_fenrir"
$env:METATRON_TTS_MODE = "premium"
[Environment]::SetEnvironmentVariable("METATRON_KOKORO_PYTHON", $Py, "User")
[Environment]::SetEnvironmentVariable("METATRON_KOKORO_MODEL", $Model, "User")
[Environment]::SetEnvironmentVariable("METATRON_KOKORO_VOICES", $Voices, "User")
[Environment]::SetEnvironmentVariable("METATRON_TTS_VOICE", "am_fenrir", "User")
[Environment]::SetEnvironmentVariable("METATRON_TTS_MODE", "premium", "User")

Write-Host "Kokoro TTS installed and configured for this qualification process and future sessions." -ForegroundColor Green
Write-Host "Precision: $Precision"
Write-Host "Python:    $Py"
Write-Host "Model:     $Model"
Write-Host "Voices:    $Voices"
