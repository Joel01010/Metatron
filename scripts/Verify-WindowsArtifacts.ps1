param([string]$BundleDir="",[switch]$RequireSigned)
$ErrorActionPreference='Stop';$Root=Split-Path -Parent $PSScriptRoot;if(-not$BundleDir){$BundleDir=Join-Path $Root 'src-tauri\target\release\bundle'}
$files=@(Get-ChildItem $BundleDir -Recurse -File -ErrorAction Stop | Where-Object {$_.Extension -in '.msi','.exe'})
if($files.Count -eq 0){throw "No Windows installer artifacts under $BundleDir"}
$rows=@();$bad=$false
foreach($f in $files){$sig=Get-AuthenticodeSignature $f.FullName;$row=[pscustomobject]@{path=$f.FullName;size=$f.Length;signature_status=[string]$sig.Status;subject=if($sig.SignerCertificate){$sig.SignerCertificate.Subject}else{$null}};$rows+=$row;if($RequireSigned -and $sig.Status -ne 'Valid'){$bad=$true}}
$out=[pscustomobject]@{schema=1;version='1.4.0';artifacts=$rows;require_signed=[bool]$RequireSigned;status=if($bad){'FAIL'}else{'PASS'}};$out|ConvertTo-Json -Depth 5
if($bad){exit 2}
