param(
  [Parameter(Mandatory=$true)][string]$CertificateThumbprint,
  [string]$InputPath = (Join-Path $PSScriptRoot '..\src-tauri\target\release\bundle'),
  [string]$TimestampUrl = 'http://timestamp.digicert.com'
)
$ErrorActionPreference='Stop'
$signtool=(Get-Command signtool.exe -ErrorAction Stop).Source
$files=Get-ChildItem -LiteralPath $InputPath -Recurse -File | Where-Object { $_.Extension -in '.exe','.msi','.msix' }
if(-not $files){ throw "No Windows signing targets found under $InputPath" }
foreach($f in $files){
  & $signtool sign /sha1 $CertificateThumbprint /fd SHA256 /tr $TimestampUrl /td SHA256 $f.FullName
  if($LASTEXITCODE -ne 0){ throw "Signing failed: $($f.FullName)" }
  & $signtool verify /pa /v $f.FullName
  if($LASTEXITCODE -ne 0){ throw "Signature verification failed: $($f.FullName)" }
}
Write-Host "Signed and verified $($files.Count) artifact(s)."
