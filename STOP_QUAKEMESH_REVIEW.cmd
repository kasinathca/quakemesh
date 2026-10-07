@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review\stop.ps1"
if errorlevel 1 (
  echo.
  echo STOP IS INCOMPLETE. Do not assume AWS resources are clean.
  pause
  exit /b 1
)
pause
