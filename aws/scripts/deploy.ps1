param(
  [string]$Region = "ap-south-1",
  [string]$Profile = "",
  [string]$SessionId = "",
  [ValidateRange(60, 240)][int]$DurationMinutes = 120,
  [string]$AwsCliPath = ""
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $Root "scripts\native_helpers.ps1")
Set-Location $Root
$AwsCli = Get-AwsCliV2Path -ExplicitPath $AwsCliPath
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

$identityResult = Invoke-NativeCommandResult -FilePath $AwsCli -ArgumentList @(
  "sts", "get-caller-identity", "--output", "json", "--no-cli-pager"
) -Quiet
$identityJson = $identityResult.Output -join [Environment]::NewLine
$identity = $identityJson | ConvertFrom-Json
if (!$identity.Account) { throw "AWS account identity is missing." }
if ($identity.Arn -match ':root$') { throw "Refusing to deploy with the AWS account root identity." }
$env:CDK_DEFAULT_ACCOUNT = $identity.Account
$env:CDK_DEFAULT_REGION = $Region

$stackProbe = Invoke-NativeCommandResult -FilePath $AwsCli -ArgumentList @(
  "cloudformation", "describe-stacks", "--stack-name", $StackName,
  "--region", $Region, "--output", "json", "--no-cli-pager"
) -AllowedExitCodes @(0, 254, 255) -Quiet
if ($stackProbe.ExitCode -eq 0) {
    throw "Refusing to overwrite existing session stack $StackName."
}
$probeText = $stackProbe.Output -join " "
if ($probeText -notmatch 'does not exist|ValidationError') {
  throw "Unable to prove that stack $StackName is absent: $probeText"
}

# Persist non-secret ownership evidence before any mutating CDK command. This
# lets STOP recover a deployment that failed before runtime config export.
$SessionDir = Join-Path $Root "artifacts\aws-v2\$SessionId"
New-Item -ItemType Directory -Force -Path $SessionDir | Out-Null
$OwnershipPath = Join-Path $SessionDir "ownership.json"
[ordered]@{
  schema_version = "2.0"
  stack_name = $StackName
  session_id = $SessionId
  account_id = [string]$identity.Account
  identity_arn = [string]$identity.Arn
  region = $Region
  expires_at = $ExpiresAt
  project = "QuakeMesh"
  architecture = "V2"
  environment = "AcademicDemo"
  ephemeral = $true
} | ConvertTo-Json | Set-Content -LiteralPath $OwnershipPath -Encoding UTF8

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

Invoke-CdkPathSafe -InfraDirectory $Infra -CdkVenv $CdkVenv -AwsCliPath $AwsCli -Profile $Profile -CdkArguments @("synth", $StackName)
Assert-CdkSynthEnvironment -InfraDirectory $Infra -StackName $StackName -Account ([string]$identity.Account) -Region $Region
$assetsManifest = Join-Path $Infra "cdk.out\$StackName.assets.json"
if (!(Test-Path -LiteralPath $assetsManifest)) { throw "CDK asset manifest is missing: $assetsManifest" }
Copy-Item -LiteralPath $assetsManifest -Destination (Join-Path $SessionDir "cdk-assets.json") -Force
Invoke-CdkPathSafe -InfraDirectory $Infra -CdkVenv $CdkVenv -AwsCliPath $AwsCli -Profile $Profile -CdkArguments (@(
  "bootstrap", "aws://$($identity.Account)/$Region"
))
Invoke-CdkPathSafe -InfraDirectory $Infra -CdkVenv $CdkVenv -AwsCliPath $AwsCli -Profile $Profile -CdkArguments (@(
  "deploy", $StackName, "--require-approval", "never"
))
if ($Profile) { $env:AWS_PROFILE = $Profile }

$ConfigPath = Join-Path $SessionDir "runtime-config.json"
$exportArguments = @("aws/scripts/export_stack_config.py", "--stack-name", $StackName, "--session-id", $SessionId, "--region", $Region, "--output", $ConfigPath)
if ($Profile) { $exportArguments += @("--profile", $Profile) }
& $RootPy @exportArguments
if ($LASTEXITCODE -ne 0) { throw "Runtime configuration export failed." }
Write-Host "AWS V2 session deployed: $StackName" -ForegroundColor Green
Write-Host "Expires at: $ExpiresAt" -ForegroundColor Yellow
Write-Host "Config (contains demo API key; gitignored): $ConfigPath" -ForegroundColor Yellow
