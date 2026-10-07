param(
    [string]$Profile = "quakemesh-demo",
    [string]$Region = "ap-south-1",
    [ValidateRange(60, 240)][int]$DurationMinutes = 180,
    [ValidateRange(4, 100)][int]$Devices = 25,
    [string]$AwsCliPath = ""
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$paths = Initialize-ReviewDirectories
Set-Location $paths.Root

function Save-State { param([hashtable]$Value) Write-ReviewState -State $Value }
function Clear-StaleLocalState {
    param([hashtable]$Value)
    if ($Value.processes) { Stop-ManagedReviewProcesses -Processes @($Value.processes) }
    Restore-AndroidReviewConfiguration
    if ($Value.runtime_config) {
        $sessionDirectory = Split-Path -Parent ([string]$Value.runtime_config)
        if (Test-Path -LiteralPath $sessionDirectory) { Remove-Item -LiteralPath $sessionDirectory -Recurse -Force }
    }
    if (Test-Path -LiteralPath $paths.State) { Remove-Item -LiteralPath $paths.State -Force }
    if (Test-Path -LiteralPath $paths.Serve) { Remove-Item -LiteralPath $paths.Serve -Recurse -Force }
}
function Ensure-Process {
    param([hashtable]$State, [string]$Name, [int]$Port, [string]$Script, [hashtable]$Arguments)
    $existing = @($State.processes | Where-Object { $_.name -eq $Name }) | Select-Object -First 1
    if ($existing) {
        $status = Get-ManagedProcessStatus -Record $existing
        if ($status.Running -and $status.Owned) { return }
        $State.processes = @($State.processes | Where-Object { $_.name -ne $Name })
    }
    if (Test-TcpPort -Port $Port) { throw "Port $Port is occupied by a process not owned by this review state." }
    $record = Start-ManagedReviewScript -Name $Name -ScriptPath $Script -Arguments $Arguments -WorkingDirectory $paths.Root
    $State.processes = @($State.processes) + @($record)
    Save-State $State
}

$branch = (& git branch --show-current).Trim()
if ($branch -ne "feature/android-v2") { throw "Review START requires feature/android-v2; current branch is $branch." }
$readinessPath = Join-Path $paths.Review "readiness.json"
if (!(Test-Path -LiteralPath $readinessPath)) { throw "Run scripts/review/prepare.ps1 once before START." }
$aws = Get-ReviewAwsContext -Profile $Profile -Region $Region -AwsCliPath $AwsCliPath
$stateObject = Read-ReviewState
$state = $null
if ($stateObject) {
    if ($stateObject.account_id -ne $aws.Account) { throw "Stored session account does not match the authenticated AWS account." }
    if ($stateObject.region -ne $Region) { throw "Stored session region does not match requested region." }
    $state = @{}
    $stateObject.psobject.Properties | ForEach-Object { $state[$_.Name] = $_.Value }
    $state.processes = @($stateObject.processes)
    $storedStack = Get-ExactStack -Context $aws -StackName ([string]$state.stack_name)
    if ($null -eq $storedStack) {
        Write-Warning "Stored session stack is absent; removing stale local metadata."
        Clear-StaleLocalState -Value $state
        $state = $null
    }
    elseif (!(Test-StackOwnership -Stack $storedStack -SessionId ([string]$state.session_id))) {
        throw "Stored stack no longer satisfies exact QuakeMesh V2 ownership checks."
    }
    elseif ([string]$storedStack.StackStatus -ne "CREATE_COMPLETE") {
        Write-Warning "Stored session is not healthy ($($storedStack.StackStatus)); cleaning it before creating a fresh session."
        & (Join-Path $PSScriptRoot "stop.ps1") -Profile $Profile -Region $Region -AwsCliPath $aws.AwsCli
        if ($LASTEXITCODE -ne 0) { throw "Recovery teardown failed." }
        $state = $null
    }
    elseif (Test-Path -LiteralPath $state.runtime_config) {
        $storedRuntime = Get-Content -LiteralPath $state.runtime_config -Raw | ConvertFrom-Json
        if ([DateTimeOffset]::Parse([string]$storedRuntime.expires_at) -lt [DateTimeOffset]::UtcNow.AddMinutes(30)) {
            Write-Warning "Stored session is expired or too close to expiry; cleaning it before creating a fresh session."
            & (Join-Path $PSScriptRoot "stop.ps1") -Profile $Profile -Region $Region -AwsCliPath $aws.AwsCli
            if ($LASTEXITCODE -ne 0) { throw "Expired-session teardown failed." }
            $state = $null
        }
    }
}
if ($null -eq $state) {
    $owned = @(Get-OwnedReviewStacks -Context $aws)
    if ($owned.Count -gt 1) { throw "Multiple owned QuakeMesh V2 stacks exist. Refusing to create or select another session." }
    if ($owned.Count -eq 1) {
        $stack = $owned[0]
        $sessionId = ([string]$stack.StackName).Substring("QuakeMesh-V2-Demo-".Length)
        $sessionDir = Join-Path $paths.Root "artifacts\aws-v2\$sessionId"
        New-Item -ItemType Directory -Force -Path $sessionDir | Out-Null
        $runtimeConfig = Join-Path $sessionDir "runtime-config.json"
        $env:AWS_PROFILE = $Profile
        $env:AWS_REGION = $Region
        & (Join-Path $paths.Root ".venv\Scripts\python.exe") aws/scripts/export_stack_config.py --stack-name $stack.StackName --session-id $sessionId --region $Region --output $runtimeConfig
        if ($LASTEXITCODE -ne 0) { throw "Failed to recover runtime metadata for the owned stack." }
        $state = [ordered]@{
            schema_version = "2.0"; session_id = $sessionId; stack_name = [string]$stack.StackName
            account_id = $aws.Account; identity_arn = $aws.Arn; region = $Region; profile = $Profile
            runtime_config = $runtimeConfig; expires_at = ((Get-Content $runtimeConfig -Raw | ConvertFrom-Json).expires_at)
            created_by_review = $false; smoke = "PENDING"; warmup = "PENDING"; processes = @()
        }
        Save-State $state
        $recoveredExpiry = [DateTimeOffset]::Parse([string]$state.expires_at)
        if ([string]$stack.StackStatus -ne "CREATE_COMPLETE" -or $recoveredExpiry -lt [DateTimeOffset]::UtcNow.AddMinutes(30)) {
            Write-Warning "Discovered session is not presentation-healthy; cleaning it before deployment."
            & (Join-Path $PSScriptRoot "stop.ps1") -Profile $Profile -Region $Region -AwsCliPath $aws.AwsCli
            if ($LASTEXITCODE -ne 0) { throw "Discovered-session recovery teardown failed." }
            $state = $null
        }
    }
}

if ($null -eq $state) {
    $sessionId = "qm-$((Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss'))-$([guid]::NewGuid().ToString('N').Substring(0,4))"
    $state = [ordered]@{
        schema_version = "2.0"; session_id = $sessionId; stack_name = "QuakeMesh-V2-Demo-$sessionId"
        account_id = $aws.Account; identity_arn = $aws.Arn; region = $Region; profile = $Profile
        runtime_config = (Join-Path $paths.Root "artifacts\aws-v2\$sessionId\runtime-config.json")
        expires_at = $null; created_by_review = $true; smoke = "PENDING"; warmup = "PENDING"; processes = @()
    }
    Save-State $state
}

$newDeployment = !(Test-Path -LiteralPath $state.runtime_config)
try {
    $localDirectory = New-DashboardVariant -Mode local
    Ensure-Process -State $state -Name "local-backend" -Port 8000 -Script (Join-Path $paths.Root "scripts\run_local.ps1") -Arguments @{}
    Wait-ReviewHttp -Uri "http://127.0.0.1:8000/health" -TimeoutSeconds 45
    Ensure-Process -State $state -Name "local-dashboard" -Port 8080 -Script (Join-Path $PSScriptRoot "serve_dashboard.ps1") -Arguments @{ Directory = $localDirectory; Port = 8080 }
    Wait-ReviewHttp -Uri "http://127.0.0.1:8080" -TimeoutSeconds 30

    if ($newDeployment) {
        & (Join-Path $paths.Root "aws\scripts\deploy.ps1") -Region $Region -Profile $Profile -SessionId $state.session_id -DurationMinutes $DurationMinutes -AwsCliPath $aws.AwsCli
        if ($LASTEXITCODE -ne 0) { throw "AWS deployment failed." }
    }
    $runtime = Get-Content -LiteralPath $state.runtime_config -Raw | ConvertFrom-Json
    if ($runtime.account_id -ne $aws.Account -or $runtime.region -ne $Region -or $runtime.session_id -ne $state.session_id) {
        throw "Runtime configuration ownership does not match the requested review session."
    }
    $state.expires_at = $runtime.expires_at
    Save-State $state
    $expires = [DateTimeOffset]::Parse([string]$runtime.expires_at)
    if ($expires -lt [DateTimeOffset]::UtcNow.AddMinutes(30)) {
        throw "Owned session is too close to expiry for a safe presentation. Run STOP and START again."
    }

    & (Join-Path $paths.Root ".venv\Scripts\python.exe") aws/scripts/smoke_test.py --config $state.runtime_config
    if ($LASTEXITCODE -ne 0) { throw "AWS smoke test failed." }
    $state.smoke = "PASS"; Save-State $state

    if ($state.warmup -ne "PASS") {
        & (Join-Path $paths.Root "aws\scripts\provision_simulators.ps1") -SessionId $state.session_id -Count $Devices -Region $Region -Profile $Profile
        if ($LASTEXITCODE -ne 0) { throw "IoT simulator provisioning failed." }
        & (Join-Path $paths.Root "aws\scripts\run_aws_scenario.ps1") -SessionId $state.session_id -Scenario distributed -Devices $Devices
        if ($LASTEXITCODE -ne 0) { throw "AWS distributed scenario process failed." }
        & (Join-Path $paths.Root ".venv\Scripts\python.exe") aws/scripts/verify_warmup.py --config $state.runtime_config --minimum-devices 4 --timeout-seconds 120
        if ($LASTEXITCODE -ne 0) { throw "AWS authoritative warm-up verification failed." }
        $state.warmup = "PASS"; Save-State $state
    }

    $awsDirectory = New-DashboardVariant -Mode aws -RuntimeConfigPath $state.runtime_config
    Ensure-Process -State $state -Name "aws-dashboard" -Port 8081 -Script (Join-Path $PSScriptRoot "serve_dashboard.ps1") -Arguments @{ Directory = $awsDirectory; Port = 8081 }
    Wait-ReviewHttp -Uri "http://127.0.0.1:8081" -TimeoutSeconds 30

    Set-AndroidReviewConfiguration -ApiBaseUrl $runtime.api_base_url -ApiKey $runtime.api_key
    Push-Location (Join-Path $paths.Root "android")
    try {
        & .\gradlew.bat assembleDebug --no-daemon
        if ($LASTEXITCODE -ne 0) { throw "Android debug APK build failed." }
    }
    finally { Pop-Location }
    $devices = @(Get-AuthorizedAdbDevices)
    $androidStatus = "NOT CONNECTED - APK READY"
    if ($devices.Count -eq 1) {
        $apk = Join-Path $paths.Root "android\app\build\outputs\apk\debug\app-debug.apk"
        Invoke-NativeCommandResult -FilePath (Get-Command adb).Source -ArgumentList @("-s", $devices[0], "install", "-r", $apk) | Out-Null
        $androidStatus = "CONNECTED / APK INSTALLED ($($devices[0]))"
    }
    elseif ($devices.Count -gt 1) { $androidStatus = "MULTIPLE DEVICES - MANUAL SELECTION: $($devices -join ', ')" }

    $state.status = "READY"; Save-State $state
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "QUAKEMESH REVIEW ENVIRONMENT READY" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Local V2: http://127.0.0.1:8080 (API http://127.0.0.1:8000)"
    Write-Host "AWS V2:   http://127.0.0.1:8081"
    Write-Host "Session:  $($state.session_id) / $Region"
    Write-Host "Smoke: PASS | Distributed warm-up: PASS | Expiry fail-safe: ARMED"
    Write-Host "Expires: $($state.expires_at)"
    Write-Host "Android: $androidStatus"
    Write-Host "STOP: double-click STOP_QUAKEMESH_REVIEW.cmd"
}
catch {
    $message = $_.Exception.Message
    Write-Host "START FAILED: $message" -ForegroundColor Red
    if ($state.created_by_review) {
        Write-Warning "START failed after deployment; attempting exact-session teardown."
        try { & (Join-Path $PSScriptRoot "stop.ps1") -Profile $Profile -Region $Region -AwsCliPath $aws.AwsCli }
        catch { Write-Warning "Automatic teardown was incomplete: $($_.Exception.Message)" }
    }
    throw
}
