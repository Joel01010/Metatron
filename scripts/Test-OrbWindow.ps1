param([int]$TimeoutSeconds=15)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MetatronWindowProbe {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr FindWindow(string c,string title);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr h,uint cmd);
}
'@
$deadline=(Get-Date).AddSeconds($TimeoutSeconds);$h=[IntPtr]::Zero
while((Get-Date)-lt$deadline -and $h -eq [IntPtr]::Zero){$h=[MetatronWindowProbe]::FindWindow($null,'Metatron Presence');if($h-eq[IntPtr]::Zero){Start-Sleep -Milliseconds 250}}
if($h-eq[IntPtr]::Zero){throw 'Metatron Presence window not found'}
$r=New-Object MetatronWindowProbe+RECT;[void][MetatronWindowProbe]::GetWindowRect($h,[ref]$r);$visible=[MetatronWindowProbe]::IsWindowVisible($h);$screens=[System.Windows.Forms.Screen]::AllScreens
$onScreen=$false;foreach($s in $screens){$b=$s.WorkingArea;if($r.Right -gt $b.Left -and $r.Left -lt $b.Right -and $r.Bottom -gt $b.Top -and $r.Top -lt $b.Bottom){$onScreen=$true;break}}
$out=[pscustomobject]@{schema=1;version='1.4.0';visible=$visible;on_screen=$onScreen;bounds=@{left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom};status=if($visible-and$onScreen){'PASS'}else{'FAIL'}};$out|ConvertTo-Json -Depth 4;if($out.status-ne'PASS'){exit 2}
