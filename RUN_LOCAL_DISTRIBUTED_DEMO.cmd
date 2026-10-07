@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_scenario.ps1" -Scenario distributed -Devices 25
if errorlevel 1 echo LOCAL DEMO FAILED.
pause
