$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
$Py=Join-Path $Root ".venv\Scripts\python.exe"
if(!(Test-Path $Py)){ throw "Run .\scripts\setup.ps1 first" }
$env:PYTHONPATH="$Root\src;$Root"
Set-Location $Root
& $Py -m local_runtime
