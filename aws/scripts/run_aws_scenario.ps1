param(
  [Parameter(Mandatory=$true)][string]$SessionId,
  [ValidateSet("isolated","same-cell","distributed","degraded")][string]$Scenario="distributed",
  [int]$Devices=25
)
$ErrorActionPreference="Stop"
$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
$Py=Join-Path $Root ".venv\Scripts\python.exe"
$SessionDir="artifacts/aws-v2/$SessionId"
$ConfigPath="$SessionDir/runtime-config.json"
if(!(Test-Path $ConfigPath)){throw "Deploy AWS V2 session first: $SessionId"}
$config=Get-Content $ConfigPath -Raw | ConvertFrom-Json
$CertDir="$SessionDir/iot-devices"
if(!(Test-Path $CertDir)){throw "Provision exact-session simulator Things first: .\aws\scripts\provision_simulators.ps1 -SessionId $SessionId -Count $Devices"}
$env:PYTHONPATH="$Root\src;$Root"
$trace="$SessionDir/traces/$Scenario.json"
& $Py -m simulator --devices $Devices --scenario $Scenario --transport mqtt --session-id $SessionId --device-prefix "QM-$SessionId-SIM" --iot-endpoint $config.iot_endpoint --cert-dir $CertDir --root-ca "$SessionDir/AmazonRootCA1.pem" --trace $trace
if($LASTEXITCODE -ne 0){throw "AWS V2 scenario failed"}
