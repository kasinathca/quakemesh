param(
 [ValidateSet("isolated","same-cell","distributed","degraded")][string]$Scenario="distributed",
 [int]$Devices=25,
 [string]$BaseUrl="http://127.0.0.1:8000",
 [int]$Seed=42
)
$ErrorActionPreference="Stop";$Root=Split-Path -Parent $PSScriptRoot;$Py=Join-Path $Root ".venv\Scripts\python.exe"
if(!(Test-Path $Py)){throw "Run .\scripts\setup.ps1 first"};$env:PYTHONPATH="$Root\src;$Root";Set-Location $Root
& $Py -m simulator --devices $Devices --scenario $Scenario --transport http --base-url $BaseUrl --seed $Seed
