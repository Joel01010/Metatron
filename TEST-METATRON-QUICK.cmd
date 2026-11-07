@echo off
setlocal
cd /d "%~dp0"
title Metatron Quick Regression Test
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\Run-MetatronTests.ps1" -Mode Quick
set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (echo METATRON QUICK TEST PASSED) else (echo METATRON QUICK TEST FAILED - exit code %CODE%)
echo Evidence is under build\self-test-* and in the matching ZIP.
pause
exit /b %CODE%
