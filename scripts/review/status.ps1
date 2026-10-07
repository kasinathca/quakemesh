param([string]$Profile = "quakemesh-demo", [string]$Region = "ap-south-1", [string]$AwsCliPath = "")
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$paths = Initialize-ReviewDirectories
$state = Read-ReviewState
Write-Host "LOCAL" -ForegroundColor Cyan
foreach ($port in @(8000,8080,8081)) { Write-Host "  Port $port`: $(if (Test-TcpPort $port) {'LISTENING'} else {'STOPPED'})" }
if ($state) {
    foreach ($record in @($state.processes)) {
        $status = Get-ManagedProcessStatus -Record $record
        Write-Host "  $($record.name) PID $($record.pid): $(if ($status.Running -and $status.Owned) {'RUNNING/OWNED'} elseif ($status.Running) {'RUNNING/NOT OWNED'} else {'STOPPED'})"
    }
}
else { Write-Host "  Review state: ABSENT" }

$aws = Get-ReviewAwsContext -Profile $Profile -Region $Region -AwsCliPath $AwsCliPath
$owned = @(Get-OwnedReviewStacks -Context $aws)
Write-Host "AWS" -ForegroundColor Cyan
Write-Host "  Identity: $($aws.Arn)"
Write-Host "  Account/region: $($aws.Account) / $Region"
Write-Host "  Active owned QuakeMesh stacks: $($owned.Count)"
foreach ($stack in $owned) { Write-Host "  $($stack.StackName): $($stack.StackStatus)" }
$bootstrap = Get-ExactStack -Context $aws -StackName "CDKToolkit"
Write-Host "  CDKToolkit: $(if ($bootstrap) {$bootstrap.StackStatus} else {'ABSENT'}) (shared, not session-owned)"
if ($state) {
    Write-Host "  Session: $($state.session_id)"
    Write-Host "  Stack status: $(if (@($owned | Where-Object { $_.StackName -eq $state.stack_name }).Count) { (@($owned | Where-Object { $_.StackName -eq $state.stack_name })[0]).StackStatus } else { 'ABSENT' })"
    Write-Host "  Expires: $($state.expires_at)"
    if (Test-Path -LiteralPath $state.runtime_config) {
        $runtime = Get-Content -LiteralPath $state.runtime_config -Raw | ConvertFrom-Json
        try {
            $health = Invoke-RestMethod -Uri ($runtime.api_base_url.TrimEnd('/') + '/health') -TimeoutSec 10
            $devices = Invoke-RestMethod -Uri ($runtime.api_base_url.TrimEnd('/') + '/v1/devices?limit=1000') -TimeoutSec 10
            $events = Invoke-RestMethod -Uri ($runtime.api_base_url.TrimEnd('/') + '/v1/events?limit=500') -TimeoutSec 10
            $alerts = Invoke-RestMethod -Uri ($runtime.api_base_url.TrimEnd('/') + '/v1/alerts?limit=2000') -TimeoutSec 10
            Write-Host "  Health: $(if ($health.data.status -eq 'ok') {'PASS'} else {'FAIL'})"
            Write-Host "  Devices/events/alerts: $(@($devices.data.items).Count) / $(@($events.data.items).Count) / $(@($alerts.data.items).Count)"
        }
        catch { Write-Host "  Health/data reads: UNAVAILABLE ($($_.Exception.Message))" -ForegroundColor Yellow }
    }
    $thingResult = Invoke-ReviewAws -Context $aws -Arguments @("iot", "list-things", "--attribute-name", "SessionId", "--attribute-value", ([string]$state.session_id), "--output", "json") -Quiet
    $thingCount = @((($thingResult.Output -join [Environment]::NewLine) | ConvertFrom-Json).things | Where-Object { $_.thingName -like "QM-$($state.session_id)-*" }).Count
    Write-Host "  Session-owned dynamic IoT Things: $thingCount"
}

Write-Host "ANDROID" -ForegroundColor Cyan
$apk = Join-Path $paths.Root "android\app\build\outputs\apk\debug\app-debug.apk"
Write-Host "  APK: $(if (Test-Path -LiteralPath $apk) {'READY'} else {'MISSING'})"
Write-Host "  ADB: $(if (Get-Command adb -ErrorAction SilentlyContinue) {'INSTALLED'} else {'MISSING'})"
$devices = @(Get-AuthorizedAdbDevices)
Write-Host "  Authorized devices: $($devices.Count)$(if ($devices.Count) { ' (' + ($devices -join ', ') + ')' } else { '' })"
Write-Host "  Current build target: $(if (Test-Path -LiteralPath $paths.AndroidMarker) {'AWS REVIEW'} else {'LOCAL/DEFAULT'})"

Write-Host "COST / CLEANUP" -ForegroundColor Cyan
Write-Host "  Last teardown: $(if (Test-Path -LiteralPath $paths.LastTeardown) { (Get-Content $paths.LastTeardown -Raw | ConvertFrom-Json).status } else { 'NONE' })"
Write-Host "  Session expiry fail-safe: $(if ($state -and $state.expires_at) { 'ARMED until ' + $state.expires_at } else { 'NO ACTIVE STATE' })"
