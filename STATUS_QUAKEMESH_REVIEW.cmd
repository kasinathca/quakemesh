@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review\status.ps1"
if errorlevel 1 echo STATUS FAILED. No cleanup action was performed.
pause
