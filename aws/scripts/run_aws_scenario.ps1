param([ValidateSet("http","mqtt")][string]$Transport="mqtt",[ValidateSet("isolated","same-cell","distributed","degraded")][string]$Scenario="distributed",[int]$Devices=25)
$ErrorActionPreference="Stop";$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..");Set-Location $Root;$Py=Join-Path $Root ".venv\Scripts\python.exe"
if(!(Test-Path artifacts/runtime-config.json)){throw "Deploy AWS first: .\aws\scripts\deploy.ps1"};$c=Get-Content artifacts/runtime-config.json | ConvertFrom-Json;$env:PYTHONPATH="$Root\src;$Root"
if($Transport -eq "http"){
 & $Py -m simulator --devices $Devices --scenario $Scenario --transport http --base-url $c.api_base_url --api-key $c.api_key
}else{
 if(!(Test-Path artifacts/iot-devices)){throw "Provision simulator Things first: .\aws\scripts\provision_simulators.ps1 -Count $Devices"}
 & $Py -m simulator --devices $Devices --scenario $Scenario --transport mqtt --iot-endpoint $c.iot_endpoint --cert-dir artifacts/iot-devices --root-ca artifacts/AmazonRootCA1.pem
}
