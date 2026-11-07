param(
    [int]$TimeoutSeconds=15,
    [string]$AppExe="",
    [string]$ScreenshotPath=""
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $PSScriptRoot
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MetatronWindowProbe {
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
  [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string c,string title);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h,out RECT r);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
}
'@

if(-not $AppExe){
    $AppExe=@(
        (Join-Path $Root 'src-tauri\target\release\metatron.exe'),
        (Join-Path $Root 'src-tauri\target\release\Metatron.exe')
    ) | Where-Object {Test-Path $_} | Select-Object -First 1
}
if(-not $AppExe){throw 'Built Metatron executable not found'}

$p=Start-Process -FilePath $AppExe -PassThru
try {
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    $h=[IntPtr]::Zero
    while((Get-Date)-lt $deadline -and $h -eq [IntPtr]::Zero){
        if($p.HasExited){throw "Metatron exited before Presence appeared: $($p.ExitCode)"}
        $h=[MetatronWindowProbe]::FindWindow([NullString]::Value,'Metatron Presence')
        if($h -eq [IntPtr]::Zero){Start-Sleep -Milliseconds 250}
    }
    if($h -eq [IntPtr]::Zero){throw 'Metatron Presence window not found'}

    # Production startup is intentionally hidden until persisted Presence settings
    # are loaded. Qualification reveals the already-created window *without
    # activation* so user settings (for example Presence disabled) cannot turn a
    # renderer/position probe into a false negative. This does not reposition it.
    if(-not [MetatronWindowProbe]::IsWindowVisible($h)){
        [MetatronWindowProbe]::ShowWindow($h,8) | Out-Null # SW_SHOWNA
        Start-Sleep -Milliseconds 300
    }

    $r=New-Object MetatronWindowProbe+RECT
    if(-not [MetatronWindowProbe]::GetWindowRect($h,[ref]$r)){throw 'Failed to read Presence window bounds'}
    $visible=[MetatronWindowProbe]::IsWindowVisible($h)
    $screens=[System.Windows.Forms.Screen]::AllScreens
    $onScreen=$false
    foreach($s in $screens){
        $b=$s.WorkingArea
        if($r.Right -gt $b.Left -and $r.Left -lt $b.Right -and $r.Bottom -gt $b.Top -and $r.Top -lt $b.Bottom){
            $onScreen=$true
            break
        }
    }

    # Presence has one deterministic default: 24 physical pixels from the
    # bottom-right of the primary monitor's work area. WinForms coordinates
    # can be DPI-virtualized on some PowerShell hosts, so allow a modest
    # tolerance while still catching random/stale placement.
    $primary=[System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $rightGap=$primary.Right-$r.Right
    $bottomGap=$primary.Bottom-$r.Bottom
    $expectedMargin=24
    $anchorTolerance=18
    $anchored=(
        [Math]::Abs($rightGap-$expectedMargin) -le $anchorTolerance -and
        [Math]::Abs($bottomGap-$expectedMargin) -le $anchorTolerance
    )
    $screenshotError=''
    if($ScreenshotPath){
        try {
            Start-Sleep -Milliseconds 800 # allow WebView2/shader first frame
            $parent=Split-Path -Parent $ScreenshotPath
            if($parent){New-Item -ItemType Directory -Force -Path $parent | Out-Null}
            $width=[Math]::Max(1,$r.Right-$r.Left); $height=[Math]::Max(1,$r.Bottom-$r.Top)
            $bmp=New-Object System.Drawing.Bitmap $width,$height
            $gfx=[System.Drawing.Graphics]::FromImage($bmp)
            try {
                $gfx.CopyFromScreen($r.Left,$r.Top,0,0,$bmp.Size)
                $bmp.Save($ScreenshotPath,[System.Drawing.Imaging.ImageFormat]::Png)
            } finally {
                $gfx.Dispose(); $bmp.Dispose()
            }
        } catch { $screenshotError=$_.Exception.Message }
    }

    $out=[pscustomobject]@{
        schema=3
        version='1.4.0'
        app_exe=$AppExe
        pid=$p.Id
        visible=$visible
        on_screen=$onScreen
        deterministic_anchor=$anchored
        expected_margin_px=$expectedMargin
        anchor_tolerance_px=$anchorTolerance
        right_gap_px=$rightGap
        bottom_gap_px=$bottomGap
        screenshot_path=$(if($ScreenshotPath){$ScreenshotPath}else{$null})
        screenshot_error=$(if($screenshotError){$screenshotError}else{$null})
        primary_work_area=@{left=$primary.Left;top=$primary.Top;right=$primary.Right;bottom=$primary.Bottom}
        bounds=@{left=$r.Left;top=$r.Top;right=$r.Right;bottom=$r.Bottom}
        status=if($visible-and$onScreen-and$anchored){'PASS'}else{'FAIL'}
    }
    $out | ConvertTo-Json -Depth 4
    if($out.status -ne 'PASS'){exit 2}
}
finally {
    if($p -and -not $p.HasExited){
        try {$p.CloseMainWindow() | Out-Null; Start-Sleep -Milliseconds 500} catch {}
        if(-not $p.HasExited){Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue}
    }
}
