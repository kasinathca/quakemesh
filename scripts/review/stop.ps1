param(
    [string]$Profile = "quakemesh-demo",
    [string]$Region = "ap-south-1",
    [string]$AwsCliPath = ""
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$paths = Initialize-ReviewDirectories
Set-Location $paths.Root
$state = Read-ReviewState

if ($state -and $state.processes) { Stop-ManagedReviewProcesses -Processes @($state.processes) }
Restore-AndroidReviewConfiguration

$aws = Get-ReviewAwsContext -Profile $Profile -Region $Region -AwsCliPath $AwsCliPath
if ($state) {
    if ($state.account_id -ne $aws.Account) { throw "Stored session account does not match authenticated AWS account." }
    if ($state.region -ne $Region) { throw "Stored session region does not match requested cleanup region." }
}
else {
    $owned = @(Get-OwnedReviewStacks -Context $aws)
    if ($owned.Count -gt 1) { throw "Multiple owned QuakeMesh stacks exist; refusing ambiguous cleanup." }
    if ($owned.Count -eq 0) {
        if (Test-Path -LiteralPath $paths.Serve) { Remove-Item -LiteralPath $paths.Serve -Recurse -Force }
        Write-Host "CLEAN: already stopped; no active owned QuakeMesh session stack was found." -ForegroundColor Green
        exit 0
    }
    $stack = $owned[0]
    $sessionId = ([string]$stack.StackName).Substring("QuakeMesh-V2-Demo-".Length)
    $sessionDir = Join-Path $paths.Root "artifacts\aws-v2\$sessionId"
    New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
    $config = Join-Path $sessionDir "runtime-config.json"
    $env:AWS_PROFILE = $Profile; $env:AWS_REGION = $Region
    & (Join-Path $paths.Root ".venv\Scripts\python.exe") aws/scripts/export_stack_config.py --stack-name $stack.StackName --session-id $sessionId --region $Region --output $config
    if ($LASTEXITCODE -ne 0) { throw "Unable to reconstruct exact-session cleanup metadata." }
    $state = [pscustomobject]@{ session_id=$sessionId; stack_name=$stack.StackName; account_id=$aws.Account; region=$Region; runtime_config=$config; processes=@() }
    Write-ReviewState -State $state
}

& (Join-Path $paths.Root "aws\scripts\destroy.ps1") -SessionId $state.session_id -Region $Region -Profile $Profile -AwsCliPath $aws.AwsCli
if ($LASTEXITCODE -ne 0) { throw "Exact-session AWS teardown failed." }
$sessionDir = Split-Path -Parent ([string]$state.runtime_config)
$report = Join-Path $sessionDir "teardown-report.json"
if (!(Test-Path -LiteralPath $report)) { throw "Teardown returned without a verification report." }
$verification = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if ($verification.status -ne "CLEAN") { throw "Teardown verification is $($verification.status), not CLEAN." }
Copy-Item -LiteralPath $report -Destination $paths.LastTeardown -Force

if (Test-Path -LiteralPath $sessionDir) { Remove-Item -LiteralPath $sessionDir -Recurse -Force }
if (Test-Path -LiteralPath $paths.Serve) { Remove-Item -LiteralPath $paths.Serve -Recurse -Force }
if (Test-Path -LiteralPath $paths.State) { Remove-Item -LiteralPath $paths.State -Force }
Write-Host "CLEAN: no known QuakeMesh session-owned AWS application resources remain." -ForegroundColor Green
Write-Host "Shared CDKToolkit bootstrap resources, if present, are reported separately and were not deleted." -ForegroundColor Yellow
