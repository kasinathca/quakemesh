@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\review\run_aws_demo.ps1"
if errorlevel 1 echo AWS DEMO FAILED.
pause
