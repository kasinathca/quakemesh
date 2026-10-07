param(
  [Parameter(Mandatory = $true)][string]$SessionId,
  [string]$Region = "ap-south-1",
  [string]$Profile = ""
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
if ($SessionId -cnotmatch '^[a-z0-9][a-z0-9-]{2,39}$') { throw "Invalid SessionId." }
if ($Profile) { $env:AWS_PROFILE = $Profile }
$env:AWS_REGION = $Region
$env:AWS_DEFAULT_REGION = $Region
$env:QM_SESSION_ID = $SessionId
$StackName = "QuakeMesh-V2-Demo-$SessionId"
$SessionDir = Join-Path $Root "artifacts\aws-v2\$SessionId"
$ConfigPath = Join-Path $SessionDir "runtime-config.json"
if (!(Test-Path $ConfigPath)) {
  throw "Refusing teardown without owned session metadata: $ConfigPath"
}
$metadata = Get-Content $ConfigPath -Raw | ConvertFrom-Json
if ($metadata.stack_name -ne $StackName -or $metadata.session_id -ne $SessionId -or $metadata.region -ne $Region) {
  throw "Session metadata does not match the requested exact teardown target."
}

$identityJson = aws sts get-caller-identity --output json
if ($LASTEXITCODE -ne 0) { throw "AWS credentials are not working." }
$identity = $identityJson | ConvertFrom-Json
if ($identity.Account -ne $metadata.account_id) { throw "AWS account does not match session ownership metadata." }
$env:CDK_DEFAULT_ACCOUNT = $identity.Account
$env:CDK_DEFAULT_REGION = $Region
$env:QM_EXPIRES_AT = $metadata.expires_at
$RootPy = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $RootPy)) { throw "Run .\scripts\setup.ps1 first." }
$ThingPrefix = "QM-$SessionId-SIM-"
$CertDir = Join-Path $SessionDir "iot-devices"
& $RootPy aws/scripts/delete_devices.py --region $Region --prefix $ThingPrefix --cert-dir $CertDir --discover
if ($LASTEXITCODE -ne 0) { throw "Exact-session IoT device cleanup failed." }

$Infra = Join-Path $Root "aws\infrastructure"
$CdkPy = Join-Path $Infra ".venv-cdk\Scripts\python.exe"
if (!(Test-Path $CdkPy)) { throw "CDK environment missing. Run deploy/setup first." }
Push-Location $Infra
try {
  $AppCmd = "`"$CdkPy`" app.py"
  npx --yes aws-cdk@2.1140.0 destroy $StackName --app $AppCmd --force
  if ($LASTEXITCODE -ne 0) { throw "CDK destroy failed." }
} finally { Pop-Location }

& $CdkPy (Join-Path $Root "aws\scripts\verify_teardown.py") --stack-name $StackName --session-id $SessionId --region $Region --output (Join-Path $SessionDir "teardown-report.json")
if ($LASTEXITCODE -ne 0) { throw "Teardown verification is INCOMPLETE. Inspect the report." }
Write-Host "CLEAN: exact session stack and owned resources are absent." -ForegroundColor Green
