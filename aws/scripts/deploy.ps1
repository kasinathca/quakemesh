param(
  [string]$Region = "ap-south-1",
  [string]$Profile = "",
  [string]$SessionId = "",
  [ValidateRange(60, 240)][int]$DurationMinutes = 120
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
if ($Profile) { $env:AWS_PROFILE = $Profile }
$env:AWS_REGION = $Region
$env:AWS_DEFAULT_REGION = $Region
if (!$SessionId) {
  $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
  $suffix = [guid]::NewGuid().ToString("N").Substring(0, 4)
  $SessionId = "qm-$stamp-$suffix"
}
if ($SessionId -cnotmatch '^[a-z0-9][a-z0-9-]{2,39}$') {
  throw "SessionId must be 3-40 lowercase letters, digits, or hyphens."
}
$ExpiresAt = (Get-Date).ToUniversalTime().AddMinutes($DurationMinutes).ToString("yyyy-MM-ddTHH:mm:ssZ")
$StackName = "QuakeMesh-V2-Demo-$SessionId"
$env:QM_SESSION_ID = $SessionId
$env:QM_EXPIRES_AT = $ExpiresAt

$identityJson = aws sts get-caller-identity --output json
if ($LASTEXITCODE -ne 0) { throw "AWS credentials are not working." }
$identity = $identityJson | ConvertFrom-Json
if (!$identity.Account) { throw "AWS account identity is missing." }
$env:CDK_DEFAULT_ACCOUNT = $identity.Account
$env:CDK_DEFAULT_REGION = $Region

aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { throw "Refusing to overwrite existing session stack $StackName." }

$RootPy = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $RootPy)) { throw "Run .\scripts\setup.ps1 first." }
Write-Host "Building Linux-compatible H3 Lambda layer" -ForegroundColor Cyan
& $RootPy aws/scripts/build_lambda_layer.py
if ($LASTEXITCODE -ne 0) { throw "Lambda layer build failed." }

$Infra = Join-Path $Root "aws\infrastructure"
$CdkVenv = Join-Path $Infra ".venv-cdk"
$CdkPy = Join-Path $CdkVenv "Scripts\python.exe"
if (!(Test-Path $CdkPy)) { & $RootPy -m venv $CdkVenv }
& $CdkPy -m pip install -r (Join-Path $Infra "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "CDK Python dependency installation failed." }

Push-Location $Infra
try {
  $AppCmd = "`"$CdkPy`" app.py"
  npx --yes aws-cdk@2.1140.0 synth $StackName --app $AppCmd
  if ($LASTEXITCODE -ne 0) { throw "CDK synth failed." }
  npx --yes aws-cdk@2.1140.0 bootstrap "aws://$($identity.Account)/$Region"
  if ($LASTEXITCODE -ne 0) { throw "CDK bootstrap failed." }
  npx --yes aws-cdk@2.1140.0 deploy $StackName --app $AppCmd --require-approval never
  if ($LASTEXITCODE -ne 0) { throw "CDK deploy failed." }
} finally { Pop-Location }

$SessionDir = Join-Path $Root "artifacts\aws-v2\$SessionId"
New-Item -ItemType Directory -Force -Path $SessionDir | Out-Null
$ConfigPath = Join-Path $SessionDir "runtime-config.json"
& $RootPy aws/scripts/export_stack_config.py --stack-name $StackName --session-id $SessionId --region $Region --output $ConfigPath
if ($LASTEXITCODE -ne 0) { throw "Runtime configuration export failed." }
Write-Host "AWS V2 session deployed: $StackName" -ForegroundColor Green
Write-Host "Expires at: $ExpiresAt" -ForegroundColor Yellow
Write-Host "Config (contains demo API key; gitignored): $ConfigPath" -ForegroundColor Yellow
