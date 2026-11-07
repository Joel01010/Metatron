@echo off
setlocal
cd /d "%~dp0"
title Metatron Full Product Qualification

echo ================================================================
echo METATRON FULL PRODUCT QUALIFICATION
echo ================================================================
echo.
echo This script prepares missing test tools when possible, provisions the
echo pinned speech and TTS runtimes, builds Metatron, verifies hardware,
echo tests the animated Presence/core/companions, runs EZSTT focus/restart/E2E,
echo performs the 60-minute memory soak, and creates one evidence ZIP.
echo.
echo Do not type or move the mouse when the EZSTT focus test announces that
 echo it is waiting for an idle desktop. The test itself will continue.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Run-MetatronTests.ps1" -Mode Full -SoakMinutes 60
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (
  echo ================================================================
  echo METATRON QUALIFICATION PASSED
  echo ================================================================
) else (
  echo ================================================================
  echo METATRON QUALIFICATION FAILED - exit code %CODE%
  echo The build\self-test-* folder and ZIP contain the evidence.
  echo ================================================================
)
echo.
pause
exit /b %CODE%
