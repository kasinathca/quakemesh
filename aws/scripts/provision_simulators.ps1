param([int]$Count=25,[string]$Region="ap-south-1",[string]$Profile="")
$ErrorActionPreference="Stop";$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..");Set-Location $Root
if($Profile){$env:AWS_PROFILE=$Profile};$env:AWS_REGION=$Region;$Py=Join-Path $Root ".venv\Scripts\python.exe";if(!(Test-Path $Py)){throw "Run scripts/setup.ps1 first"}
& $Py aws/scripts/provision_devices.py --count $Count --region $Region
Write-Host "Certificates are under artifacts/iot-devices and are gitignored." -ForegroundColor Green
