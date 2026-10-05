param([string]$Region="ap-south-1",[string]$Profile="")
$ErrorActionPreference="Stop";$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..");Set-Location $Root
if($Profile){$env:AWS_PROFILE=$Profile};$env:AWS_REGION=$Region;$env:AWS_DEFAULT_REGION=$Region
$identity=aws sts get-caller-identity --output json | ConvertFrom-Json
if(!$identity.Account){throw "AWS credentials are not working"};$env:CDK_DEFAULT_ACCOUNT=$identity.Account;$env:CDK_DEFAULT_REGION=$Region
$RootPy=Join-Path $Root ".venv\Scripts\python.exe";if(!(Test-Path $RootPy)){throw "Run .\scripts\setup.ps1 first"}
Write-Host "Building Linux-compatible H3 Lambda layer" -ForegroundColor Cyan
& $RootPy aws/scripts/build_lambda_layer.py
$Infra=Join-Path $Root "aws\infrastructure";$CdkVenv=Join-Path $Infra ".venv-cdk";$CdkPy=Join-Path $CdkVenv "Scripts\python.exe"
if(!(Test-Path $CdkPy)){& $RootPy -m venv $CdkVenv}
& $CdkPy -m pip install --upgrade pip
& $CdkPy -m pip install -r (Join-Path $Infra "requirements.txt")
Push-Location $Infra
try {
  $AppCmd="`"$CdkPy`" app.py"
  Write-Host "Synthesizing with CDK interpreter: $CdkPy" -ForegroundColor Cyan
  npx --yes aws-cdk@2.1140.0 synth --app $AppCmd
  npx --yes aws-cdk@2.1140.0 bootstrap "aws://$($identity.Account)/$Region"
  npx --yes aws-cdk@2.1140.0 deploy QuakeMeshStack --app $AppCmd --require-approval never
} finally {Pop-Location}
& $RootPy aws/scripts/export_stack_config.py
$config=Get-Content artifacts/runtime-config.json | ConvertFrom-Json
@"
window.QUAKEMESH_CONFIG = { apiBaseUrl: "$($config.api_base_url)", modeLabel: "AWS $Region" };
"@ | Set-Content dashboard/config.aws.js -Encoding UTF8
Write-Host "AWS deployed. Account-specific runtime configuration: artifacts/runtime-config.json" -ForegroundColor Green
Write-Host "Do not commit that file; it contains the controlled-demo API key." -ForegroundColor Yellow
