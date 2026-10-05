param([int]$Port=8080)
$ErrorActionPreference="Stop"
$Root=Split-Path -Parent $PSScriptRoot
$Py=Join-Path $Root ".venv\Scripts\python.exe"
if(!(Test-Path $Py)){ $Py=(Get-Command python -ErrorAction Stop).Source }
Set-Location $Root
Write-Host "Dashboard: http://127.0.0.1:$Port" -ForegroundColor Cyan
& $Py -m http.server $Port --bind 127.0.0.1 --directory dashboard
