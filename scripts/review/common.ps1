Set-StrictMode -Version Latest

$script:ReviewRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $script:ReviewRoot "scripts\native_helpers.ps1")
. (Join-Path $script:ReviewRoot "scripts\process_helpers.ps1")

function Get-ReviewPaths {
    $review = Join-Path $script:ReviewRoot "artifacts\review"
    return [pscustomobject]@{
        Root = $script:ReviewRoot
        Review = $review
        State = Join-Path $review "current-session.json"
        LastTeardown = Join-Path $review "last-teardown.json"
        Logs = Join-Path $review "logs"
        Serve = Join-Path $review "serve"
        AndroidBackup = Join-Path $review "android-local.properties.backup"
        AndroidMarker = Join-Path $review "android-local.properties.state.json"
    }
}

function Initialize-ReviewDirectories {
    $paths = Get-ReviewPaths
    foreach ($directory in @($paths.Review, $paths.Logs, $paths.Serve)) {
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
    }
    return $paths
}

function Read-ReviewState {
    $paths = Get-ReviewPaths
    if (!(Test-Path -LiteralPath $paths.State -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $paths.State -Raw | ConvertFrom-Json
}

function Write-ReviewState {
    param([Parameter(Mandatory = $true)][object]$State)
    $paths = Initialize-ReviewDirectories
    $temporary = "$($paths.State).tmp"
    $State | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $paths.State -Force
}

function Get-ReviewAwsContext {
    param(
        [string]$Profile = "quakemesh-demo",
        [string]$Region = "ap-south-1",
        [string]$AwsCliPath = ""
    )
    $aws = Get-AwsCliV2Path -ExplicitPath $AwsCliPath
    $arguments = @("sts", "get-caller-identity", "--output", "json", "--region", $Region, "--no-cli-pager")
    if ($Profile) { $arguments += @("--profile", $Profile) }
    $result = Invoke-NativeCommandResult -FilePath $aws -ArgumentList $arguments -Quiet
    $identity = ($result.Output -join [Environment]::NewLine) | ConvertFrom-Json
    if (!$identity.Account -or !$identity.Arn) { throw "AWS STS returned an incomplete identity." }
    if ($identity.Arn -match ':root$') { throw "Refusing to use the AWS account root identity." }
    return [pscustomobject]@{
        AwsCli = $aws
        Profile = $Profile
        Region = $Region
        Account = [string]$identity.Account
        Arn = [string]$identity.Arn
    }
}

function Invoke-ReviewAws {
    param(
        [Parameter(Mandatory = $true)][object]$Context,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [int[]]$AllowedExitCodes = @(0),
        [switch]$Quiet
    )
    $all = @($Arguments)
    if ($Context.Region -and "--region" -notin $all) { $all += @("--region", $Context.Region) }
    if ($Context.Profile -and "--profile" -notin $all) { $all += @("--profile", $Context.Profile) }
    if ("--no-cli-pager" -notin $all) { $all += "--no-cli-pager" }
    return Invoke-NativeCommandResult `
        -FilePath $Context.AwsCli `
        -ArgumentList $all `
        -AllowedExitCodes $AllowedExitCodes `
        -Quiet:$Quiet
}

function Get-ExactStack {
    param([object]$Context, [string]$StackName)
    $probe = Invoke-ReviewAws -Context $Context -Arguments @(
        "cloudformation", "describe-stacks", "--stack-name", $StackName, "--output", "json"
    ) -AllowedExitCodes @(0, 254, 255) -Quiet
    if ($probe.ExitCode -eq 0) {
        $document = ($probe.Output -join [Environment]::NewLine) | ConvertFrom-Json
        $stack = @($document.Stacks)[0]
        return ,$stack
    }
    if (($probe.Output -join " ") -match 'does not exist|ValidationError') { return $null }
    throw "Unable to determine stack state for $StackName`: $($probe.Output -join ' ')"
}

function Test-StackOwnership {
    param([object]$Stack, [string]$SessionId)
    if ($null -eq $Stack -or $Stack.StackName -ne "QuakeMesh-V2-Demo-$SessionId") { return $false }
    $tags = @{}
    foreach ($tag in $Stack.Tags) { $tags[[string]$tag.Key] = [string]$tag.Value }
    return (
        $tags.Project -eq "QuakeMesh" -and
        $tags.Architecture -eq "V2" -and
        $tags.Environment -eq "AcademicDemo" -and
        $tags.Ephemeral -eq "true" -and
        $tags.SessionId -eq $SessionId
    )
}

function Get-OwnedReviewStacks {
    param([object]$Context)
    $result = Invoke-ReviewAws -Context $Context -Arguments @(
        "cloudformation", "list-stacks", "--stack-status-filter",
        "CREATE_IN_PROGRESS", "CREATE_COMPLETE", "CREATE_FAILED", "ROLLBACK_IN_PROGRESS",
        "ROLLBACK_FAILED", "ROLLBACK_COMPLETE", "DELETE_FAILED", "UPDATE_IN_PROGRESS",
        "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS", "UPDATE_COMPLETE", "UPDATE_FAILED",
        "UPDATE_ROLLBACK_IN_PROGRESS", "UPDATE_ROLLBACK_FAILED", "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS",
        "UPDATE_ROLLBACK_COMPLETE", "IMPORT_IN_PROGRESS", "IMPORT_COMPLETE", "IMPORT_ROLLBACK_IN_PROGRESS",
        "IMPORT_ROLLBACK_FAILED", "IMPORT_ROLLBACK_COMPLETE", "DELETE_IN_PROGRESS", "--output", "json"
    ) -Quiet
    $summaries = (($result.Output -join [Environment]::NewLine) | ConvertFrom-Json).StackSummaries
    $owned = @()
    foreach ($summary in $summaries) {
        if ([string]$summary.StackName -notlike "QuakeMesh-V2-Demo-*") { continue }
        $sessionId = ([string]$summary.StackName).Substring("QuakeMesh-V2-Demo-".Length)
        $stack = Get-ExactStack -Context $Context -StackName ([string]$summary.StackName)
        if (Test-StackOwnership -Stack $stack -SessionId $sessionId) {
            $owned += $stack
        }
        else {
            throw "Found a QuakeMesh-prefixed stack without complete V2 ownership tags: $($summary.StackName). Refusing automatic lifecycle action."
        }
    }
    return @($owned)
}

function Test-TcpPort {
    param([int]$Port)
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        return $async.AsyncWaitHandle.WaitOne(300) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

function Get-ManagedProcessStatus {
    param([object]$Record)
    try { $process = Get-Process -Id ([int]$Record.pid) -ErrorAction Stop }
    catch { return [pscustomobject]@{ Running = $false; Owned = $false; Process = $null } }
    $commandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($Record.pid)" -ErrorAction Stop).CommandLine
    $owned = $commandLine -and $commandLine.Contains([string]$Record.command_token)
    return [pscustomobject]@{ Running = $true; Owned = [bool]$owned; Process = $process }
}

function Get-ManagedProcessTree {
    param([int]$RootPid)
    # Snapshot before terminating the wrapper. Windows child processes can
    # outlive their parent, so STOP must terminate verified descendants first.
    $rows = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    $result = @()
    $queue = @([pscustomobject]@{ Pid = $RootPid; Depth = 0 })
    while ($queue.Count -gt 0) {
        $current = $queue[0]
        $queue = @($queue | Select-Object -Skip 1)
        $result += $current
        foreach ($child in @($rows | Where-Object { [int]$_.ParentProcessId -eq [int]$current.Pid })) {
            $queue += [pscustomobject]@{ Pid = [int]$child.ProcessId; Depth = ([int]$current.Depth + 1) }
        }
    }
    return @($result | Sort-Object Depth -Descending)
}

function Start-ManagedReviewScript {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [hashtable]$Arguments,
        [string]$WorkingDirectory
    )
    $paths = Initialize-ReviewDirectories
    $encoded = New-EncodedPowerShellScriptCommand -ScriptPath $ScriptPath -NamedArguments $Arguments
    $stdout = Join-Path $paths.Logs "$Name.out.log"
    $stderr = Join-Path $paths.Logs "$Name.err.log"
    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded) `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr `
        -PassThru
    return [ordered]@{
        name = $Name
        pid = $process.Id
        command_token = $encoded
        script = $ScriptPath
        started_at = (Get-Date).ToUniversalTime().ToString("o")
        stdout = $stdout
        stderr = $stderr
    }
}

function Stop-ManagedReviewProcesses {
    param([object[]]$Processes)
    foreach ($record in @($Processes)) {
        $status = Get-ManagedProcessStatus -Record $record
        if (!$status.Running) { continue }
        if (!$status.Owned) {
            throw "Refusing to stop PID $($record.pid); it no longer matches review-owned process $($record.name)."
        }
        $tree = @(Get-ManagedProcessTree -RootPid ([int]$record.pid))
        foreach ($node in $tree) {
            $process = Get-Process -Id ([int]$node.Pid) -ErrorAction SilentlyContinue
            if (!$process) { continue }
            Stop-Process -Id ([int]$node.Pid) -Force -ErrorAction Stop
            $process.WaitForExit(10000) | Out-Null
        }
    }
}

function Wait-ReviewHttp {
    param([string]$Uri, [int]$TimeoutSeconds = 45)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return }
        }
        catch { Start-Sleep -Milliseconds 500 }
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for $Uri"
}

function New-DashboardVariant {
    param([ValidateSet("local", "aws")][string]$Mode, [string]$RuntimeConfigPath = "")
    $paths = Initialize-ReviewDirectories
    $source = Join-Path $script:ReviewRoot "dashboard\dist"
    if (!(Test-Path -LiteralPath (Join-Path $source "index.html"))) {
        throw "Dashboard build is missing. Run scripts/review/prepare.ps1 first."
    }
    $target = Join-Path $paths.Serve $Mode
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -Path (Join-Path $source "*") -Destination $target -Recurse -Force
    if ($Mode -eq "local") {
        Copy-Item -LiteralPath (Join-Path $script:ReviewRoot "dashboard\public\config.js") -Destination (Join-Path $target "config.js") -Force
    }
    else {
        $runtime = Get-Content -LiteralPath $RuntimeConfigPath -Raw | ConvertFrom-Json
        $config = [ordered]@{
            apiBaseUrl = $runtime.api_base_url
            apiKey = $runtime.api_key
            environmentLabel = "AWS V2 Demo"
            region = $runtime.region
            sessionId = $runtime.session_id
            expiresAt = $runtime.expires_at
        } | ConvertTo-Json -Compress
        Set-Content -LiteralPath (Join-Path $target "config.js") -Value "window.QUAKEMESH_CONFIG = $config;" -Encoding UTF8
    }
    return $target
}

function Set-AndroidReviewConfiguration {
    param([string]$ApiBaseUrl, [string]$ApiKey)
    $paths = Initialize-ReviewDirectories
    $localProperties = Join-Path $script:ReviewRoot "android\local.properties"
    $existed = Test-Path -LiteralPath $localProperties
    if ($existed -and !(Test-Path -LiteralPath $paths.AndroidMarker)) {
        Copy-Item -LiteralPath $localProperties -Destination $paths.AndroidBackup -Force
    }
    $lines = @()
    if ($existed) { $lines = @(Get-Content -LiteralPath $localProperties) }
    $lines = @($lines | Where-Object { $_ -notmatch '^QUAKEMESH_(API_BASE_URL|API_KEY)=' })
    $lines += "QUAKEMESH_API_BASE_URL=$ApiBaseUrl"
    $lines += "QUAKEMESH_API_KEY=$ApiKey"
    $lines | Set-Content -LiteralPath $localProperties -Encoding ASCII
    [ordered]@{ existed = $existed; configured_at = (Get-Date).ToUniversalTime().ToString("o") } |
        ConvertTo-Json | Set-Content -LiteralPath $paths.AndroidMarker -Encoding UTF8
}

function Restore-AndroidReviewConfiguration {
    $paths = Get-ReviewPaths
    if (!(Test-Path -LiteralPath $paths.AndroidMarker)) { return }
    $state = Get-Content -LiteralPath $paths.AndroidMarker -Raw | ConvertFrom-Json
    $localProperties = Join-Path $script:ReviewRoot "android\local.properties"
    if ($state.existed -and (Test-Path -LiteralPath $paths.AndroidBackup)) {
        Copy-Item -LiteralPath $paths.AndroidBackup -Destination $localProperties -Force
    }
    elseif (Test-Path -LiteralPath $localProperties) {
        $lines = @(Get-Content -LiteralPath $localProperties | Where-Object { $_ -notmatch '^QUAKEMESH_(API_BASE_URL|API_KEY)=' })
        $lines | Set-Content -LiteralPath $localProperties -Encoding ASCII
    }
    Remove-Item -LiteralPath $paths.AndroidMarker -Force
    if (Test-Path -LiteralPath $paths.AndroidBackup) { Remove-Item -LiteralPath $paths.AndroidBackup -Force }
}

function Get-AuthorizedAdbDevices {
    $adb = @(Get-Command adb -All -ErrorAction SilentlyContinue) | Select-Object -First 1
    if (!$adb) { return @() }
    # Do not start or mutate an ADB daemon as part of an AWS review. A phone is
    # optional; inspect devices only when a user-started daemon already exists.
    if (!(Test-TcpPort -Port 5037)) { return @() }
    try {
        $output = @(& ([string]$adb.Source) devices -l 2>&1)
        if ($LASTEXITCODE -ne 0) { throw "adb devices exited with code $LASTEXITCODE" }
    }
    catch {
        Write-Warning "ADB is unavailable; continuing with APK READY and no connected phone. $($_.Exception.Message)"
        return @()
    }
    return @($output | Where-Object { $_ -match '^\S+\s+device(?:\s|$)' } | ForEach-Object { ($_ -split '\s+')[0] })
}
