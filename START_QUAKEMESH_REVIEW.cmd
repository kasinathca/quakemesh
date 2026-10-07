@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review\start.ps1"
if errorlevel 1 (
  echo.
  echo START FAILED. Review the error above; exact-session cleanup was attempted when safe.
  pause
  exit /b 1
)
pause
