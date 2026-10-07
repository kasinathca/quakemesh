@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review\prepare.ps1" -Bootstrap
if errorlevel 1 (
  echo.
  echo PREPARATION FAILED. Review the error above; no QuakeMesh demo session was intentionally left running.
  pause
  exit /b 1
)
pause
