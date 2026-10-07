param(
    [string]$Profile = "quakemesh-demo",
    [string]$Region = "ap-south-1",
    [string]$AwsCliPath = "",
    [switch]$Bootstrap
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$paths = Initialize-ReviewDirectories
Set-Location $paths.Root

$branch = (& git branch --show-current).Trim()
if ($branch -ne "feature/android-v2") { throw "Review preparation requires feature/android-v2; current branch is $branch." }
$python = Join-Path $paths.Root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $python)) { throw "Python environment missing. Run scripts/setup.ps1 first." }
foreach ($command in @("node", "npm", "npx", "java")) {
    if (!(Get-Command $command -ErrorAction SilentlyContinue)) { throw "Required command is missing: $command" }
}
& $python -c "import boto3,h3,fastapi; print('Python dependencies: PASS')"
if ($LASTEXITCODE -ne 0) { throw "Python dependency validation failed." }

$aws = Get-ReviewAwsContext -Profile $Profile -Region $Region -AwsCliPath $AwsCliPath
Write-Host "AWS identity: $($aws.Arn)" -ForegroundColor Cyan
Write-Host "AWS account/region: $($aws.Account) / $Region" -ForegroundColor Cyan

& (Join-Path $paths.Root "scripts\validate.ps1")
if ($LASTEXITCODE -ne 0) { throw "Repository validation failed." }

Push-Location (Join-Path $paths.Root "android")
try {
    & .\gradlew.bat testDebugUnitTest assembleDebug lintDebug --no-daemon
    if ($LASTEXITCODE -ne 0) { throw "Android preparation failed." }
}
finally { Pop-Location }

& $python (Join-Path $paths.Root "aws\scripts\build_lambda_layer.py")
if ($LASTEXITCODE -ne 0) { throw "Lambda H3 layer build failed." }

$infra = Join-Path $paths.Root "aws\infrastructure"
$cdkVenv = Join-Path $infra ".venv-cdk"
$cdkPython = Join-Path $cdkVenv "Scripts\python.exe"
if (!(Test-Path -LiteralPath $cdkPython)) { & $python -m venv $cdkVenv }
& $cdkPython -m pip install -r (Join-Path $infra "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "CDK Python dependency preparation failed." }
$env:QM_SESSION_ID = "review-prepare"
$env:QM_EXPIRES_AT = (Get-Date).ToUniversalTime().AddHours(4).ToString("yyyy-MM-ddTHH:mm:ssZ")
$env:CDK_DEFAULT_ACCOUNT = $aws.Account
$env:CDK_DEFAULT_REGION = $Region
$env:AWS_PROFILE = $Profile
$env:AWS_REGION = $Region
$env:AWS_DEFAULT_REGION = $Region
Invoke-CdkPathSafe -InfraDirectory $infra -CdkVenv $cdkVenv -AwsCliPath $aws.AwsCli -Profile $Profile -CdkArguments @(
    "synth", "QuakeMesh-V2-Demo-review-prepare", "--quiet"
)
Assert-CdkSynthEnvironment -InfraDirectory $infra -StackName "QuakeMesh-V2-Demo-review-prepare" -Account $aws.Account -Region $Region

$toolkitStack = Get-ExactStack -Context $aws -StackName "CDKToolkit"
if ($null -eq $toolkitStack -and $Bootstrap) {
    Invoke-CdkPathSafe -InfraDirectory $infra -CdkVenv $cdkVenv -AwsCliPath $aws.AwsCli -Profile $Profile -CdkArguments @(
        "bootstrap", "aws://$($aws.Account)/$Region"
    )
    $toolkitStack = Get-ExactStack -Context $aws -StackName "CDKToolkit"
}
if ($null -eq $toolkitStack) {
    Write-Warning "CDKToolkit is absent. START can bootstrap it, but prepare.ps1 -Bootstrap is recommended before presentation day."
}
else {
    Write-Host "CDKToolkit: PRESENT (shared bootstrap infrastructure; not a QuakeMesh session resource)" -ForegroundColor Yellow
}

& $python (Join-Path $paths.Root "scripts\check_secrets.py")
if ($LASTEXITCODE -ne 0) { throw "Secret scan failed." }
& git diff --check
if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }

$readiness = [ordered]@{
    schema_version = "2.0"
    status = "READY_FOR_START"
    prepared_at = (Get-Date).ToUniversalTime().ToString("o")
    commit = (& git rev-parse HEAD).Trim()
    branch = $branch
    account_id = $aws.Account
    identity_arn = $aws.Arn
    region = $Region
    aws_cli = $aws.AwsCli
    cdk_toolkit = $(if ($null -eq $toolkitStack) { "ABSENT" } else { [string]$toolkitStack.StackStatus })
    adb = [bool](Get-Command adb -ErrorAction SilentlyContinue)
}
$readiness | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $paths.Review "readiness.json") -Encoding UTF8
Write-Host "========================================" -ForegroundColor Green
Write-Host "QUAKEMESH REVIEW PREPARATION PASSED" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "No QuakeMesh demo session was deployed."
Write-Host "Readiness report: $(Join-Path $paths.Review 'readiness.json')"
