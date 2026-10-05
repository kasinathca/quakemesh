param([string]$Region="ap-south-1",[string]$Profile="")
$ErrorActionPreference="Stop";$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..");Set-Location $Root;if($Profile){$env:AWS_PROFILE=$Profile};$env:AWS_REGION=$Region;$env:AWS_DEFAULT_REGION=$Region
$Py=Join-Path $Root ".venv\Scripts\python.exe";if(!(Test-Path $Py)){throw "Run .\scripts\setup.ps1 first"};& $Py aws/scripts/delete_devices.py --region $Region --discover
$Infra=Join-Path $Root "aws\infrastructure";$CdkPy=Join-Path $Infra ".venv-cdk\Scripts\python.exe";if(!(Test-Path $CdkPy)){throw "CDK environment missing. Deploy/setup it first."}
$identity=aws sts get-caller-identity --output json | ConvertFrom-Json;$env:CDK_DEFAULT_ACCOUNT=$identity.Account;$env:CDK_DEFAULT_REGION=$Region;Push-Location $Infra
try{$AppCmd="`"$CdkPy`" app.py";npx --yes aws-cdk@2.1140.0 destroy QuakeMeshStack --app $AppCmd --force}finally{Pop-Location}
Write-Host "Stack destroyed. The S3 experiment archive uses RETAIN by design; delete it manually only if you no longer need its evidence." -ForegroundColor Yellow
