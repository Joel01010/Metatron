param(
  [string]$Root = "",
  [ValidateSet("q4_k_m","f16")][string]$Precision = "q4_k_m",
  [string]$Revision = "v1",
  [string]$Python = "python"
)
$ErrorActionPreference='Stop'
if(-not $Root){$base=if($env:LOCALAPPDATA){$env:LOCALAPPDATA}else{Join-Path $HOME 'AppData\Local'};$Root=Join-Path $base 'Metatron\s1-mini'}
$Root=[IO.Path]::GetFullPath($Root); New-Item -ItemType Directory -Force -Path $Root | Out-Null
$venv=Join-Path $Root 'venv'; if(-not(Test-Path (Join-Path $venv 'Scripts\python.exe'))){& $Python -m venv $venv}
$python=Join-Path $venv 'Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install huggingface_hub llama-cpp-python
$file=if($Precision -eq 'q4_k_m'){'s1-mini-q4_k_m.gguf'}else{'s1-mini-f16.gguf'}
$model=Join-Path $Root $file
if(-not(Test-Path $model)){
  & $python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download('superwhisper/s1-mini-GGUF', '$file', revision='$Revision', local_dir=r'$Root'))"
}
$worker=Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts\s1_llamacpp_worker.py'
Write-Host 'S1-mini by Superwhisper runtime ready.' -ForegroundColor Green
Write-Host "Set METATRON_S1_CMD to: `"$python`" `"$worker`" --model `"$model`""
Write-Host 'Default releases do not redistribute these weights; preserve LICENSE/NOTICE and the required model name if you redistribute them.'
