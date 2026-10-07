param(
  [Parameter(Mandatory = $true)][string]$SessionId,
  [string]$Region = "ap-south-1",
  [string]$Profile = "",
  [string]$AwsCliPath = ""
)
$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
. (Join-Path $Root "scripts\native_helpers.ps1")
Set-Location $Root
$AwsCli = Get-AwsCliV2Path -ExplicitPath $AwsCliPath
if ($SessionId -cnotmatch '^[a-z0-9][a-z0-9-]{2,39}$') { throw "Invalid SessionId." }
if ($Profile) { $env:AWS_PROFILE = $Profile }
$env:AWS_REGION = $Region
$env:AWS_DEFAULT_REGION = $Region
$env:QM_SESSION_ID = $SessionId
$StackName = "QuakeMesh-V2-Demo-$SessionId"
$SessionDir = Join-Path $Root "artifacts\aws-v2\$SessionId"
$ConfigPath = Join-Path $SessionDir "runtime-config.json"
$OwnershipPath = Join-Path $SessionDir "ownership.json"
$MetadataPath = if (Test-Path -LiteralPath $ConfigPath) { $ConfigPath } else { $OwnershipPath }
if (!(Test-Path -LiteralPath $MetadataPath)) {
  throw "Refusing teardown without owned session metadata: $OwnershipPath"
}
$metadata = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
if ($metadata.stack_name -ne $StackName -or $metadata.session_id -ne $SessionId -or $metadata.region -ne $Region) {
  throw "Session metadata does not match the requested exact teardown target."
}

$identityResult = Invoke-NativeCommandResult -FilePath $AwsCli -ArgumentList @(
  "sts", "get-caller-identity", "--output", "json", "--no-cli-pager"
) -Quiet
$identityJson = $identityResult.Output -join [Environment]::NewLine
$identity = $identityJson | ConvertFrom-Json
if ($identity.Arn -match ':root$') { throw "Refusing teardown with the AWS account root identity." }
if ($identity.Account -ne $metadata.account_id) { throw "AWS account does not match session ownership metadata." }
$env:CDK_DEFAULT_ACCOUNT = $identity.Account
$env:CDK_DEFAULT_REGION = $Region
$env:QM_EXPIRES_AT = $metadata.expires_at

$stackProbe = Invoke-NativeCommandResult -FilePath $AwsCli -ArgumentList @(
  "cloudformation", "describe-stacks", "--stack-name", $StackName,
  "--region", $Region, "--output", "json", "--no-cli-pager"
) -AllowedExitCodes @(0, 254, 255) -Quiet
if ($stackProbe.ExitCode -eq 0) {
  $stack = (($stackProbe.Output -join [Environment]::NewLine) | ConvertFrom-Json).Stacks[0]
  $tags = @{}
  foreach ($tag in $stack.Tags) { $tags[[string]$tag.Key] = [string]$tag.Value }
  if ($tags.Project -ne "QuakeMesh" -or $tags.Architecture -ne "V2" -or
      $tags.Environment -ne "AcademicDemo" -or $tags.Ephemeral -ne "true" -or
      $tags.SessionId -ne $SessionId) {
    throw "Refusing teardown because stack ownership tags are incomplete or do not match the exact session."
  }
  $inventoryResult = Invoke-NativeCommandResult -FilePath $AwsCli -ArgumentList @(
    "cloudformation", "list-stack-resources", "--stack-name", $StackName,
    "--region", $Region, "--output", "json", "--no-cli-pager"
  ) -Quiet
  $inventoryPath = Join-Path $SessionDir "resource-inventory.json"
  $inventoryDocument = ($inventoryResult.Output -join [Environment]::NewLine) | ConvertFrom-Json
  [ordered]@{
    schema_version = "2.0"
    stack_name = $StackName
    session_id = $SessionId
    captured_at = (Get-Date).ToUniversalTime().ToString("o")
    resources = @($inventoryDocument.StackResourceSummaries | ForEach-Object {
      [ordered]@{
        logical_id = [string]$_.LogicalResourceId
        physical_id = [string]$_.PhysicalResourceId
        type = [string]$_.ResourceType
      }
    })
  } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $inventoryPath -Encoding UTF8
}
elseif (($stackProbe.Output -join " ") -notmatch 'does not exist|ValidationError') {
  throw "Unable to prove exact stack state before teardown: $($stackProbe.Output -join ' ')"
}
$RootPy = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $RootPy)) { throw "Run .\scripts\setup.ps1 first." }
$ThingPrefix = "QM-$SessionId-SIM-"
$CertDir = Join-Path $SessionDir "iot-devices"
& $RootPy aws/scripts/delete_devices.py --region $Region --prefix $ThingPrefix --cert-dir $CertDir --discover
if ($LASTEXITCODE -ne 0) { throw "Exact-session IoT device cleanup failed." }
if (Test-Path -LiteralPath $ConfigPath) {
  & $RootPy aws/scripts/delete_sns_endpoints.py --config $ConfigPath
  if ($LASTEXITCODE -ne 0) { throw "Exact-session SNS endpoint cleanup failed." }
}

$Infra = Join-Path $Root "aws\infrastructure"
$CdkVenv = Join-Path $Infra ".venv-cdk"
$CdkPy = Join-Path $CdkVenv "Scripts\python.exe"
if (!(Test-Path $CdkPy)) { throw "CDK environment missing. Run deploy/setup first." }
Invoke-CdkPathSafe -InfraDirectory $Infra -CdkVenv $CdkVenv -AwsCliPath $AwsCli -Profile $Profile -CdkArguments (@(
  "destroy", $StackName, "--force"
))

$verifyArguments = @(
  (Join-Path $Root "aws\scripts\verify_teardown.py"),
  "--stack-name", $StackName,
  "--session-id", $SessionId,
  "--region", $Region,
  "--output", (Join-Path $SessionDir "teardown-report.json")
)
if (Test-Path -LiteralPath $ConfigPath) { $verifyArguments += @("--runtime-config", $ConfigPath) }
if (Test-Path -LiteralPath (Join-Path $SessionDir "resource-inventory.json")) {
  $verifyArguments += @("--resource-inventory", (Join-Path $SessionDir "resource-inventory.json"))
}
if (Test-Path -LiteralPath (Join-Path $SessionDir "cdk-assets.json")) {
  $verifyArguments += @("--cdk-assets", (Join-Path $SessionDir "cdk-assets.json"))
}
& $CdkPy @verifyArguments
if ($LASTEXITCODE -ne 0) { throw "Teardown verification is INCOMPLETE. Inspect the report." }
Write-Host "CLEAN: exact session stack and owned resources are absent." -ForegroundColor Green
