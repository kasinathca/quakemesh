param([Parameter(Mandatory=$true)][string]$SessionId,[int]$Count=25,[string]$Region="ap-south-1",[string]$Profile="")
$ErrorActionPreference="Stop";$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..");Set-Location $Root
if($Profile){$env:AWS_PROFILE=$Profile};$env:AWS_REGION=$Region;$Py=Join-Path $Root ".venv\Scripts\python.exe";if(!(Test-Path $Py)){throw "Run scripts/setup.ps1 first"}
$Config="artifacts/aws-v2/$SessionId/runtime-config.json";if(!(Test-Path $Config)){throw "Deploy the exact session first: $SessionId"}
$Prefix="QM-$SessionId-SIM-";$Out="artifacts/aws-v2/$SessionId/iot-devices"
$arguments=@("aws/scripts/provision_devices.py","--count",$Count,"--region",$Region,"--session-id",$SessionId,"--out",$Out,"--prefix",$Prefix)
if($Profile){$arguments+=@("--profile",$Profile)}
& $Py @arguments
if($LASTEXITCODE -ne 0){throw "Simulator provisioning failed"}
Write-Host "Certificates are under $Out and are gitignored." -ForegroundColor Green
