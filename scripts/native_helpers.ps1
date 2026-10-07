Set-StrictMode -Version Latest

function Invoke-NativeCommandResult {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int[]]$AllowedExitCodes = @(0),
        [switch]$Quiet
    )

    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5 can promote a native process' stderr to a
        # NativeCommandError when the caller uses Stop. Scope the relaxation to
        # this one invocation and always restore the caller's preference.
        $ErrorActionPreference = "Continue"
        $output = @(& $FilePath @ArgumentList 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }

    if (!$Quiet -and $output.Count -gt 0) {
        $output | ForEach-Object { Write-Host ([string]$_) }
    }
    if ($exitCode -notin $AllowedExitCodes) {
        $rendered = $ArgumentList -join " "
        $detail = ($output | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        throw "Native command failed with exit code $exitCode`: $FilePath $rendered$([Environment]::NewLine)$detail"
    }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output | ForEach-Object { [string]$_ })
    }
}

function Get-AwsCliV2Path {
    param([string]$ExplicitPath = "")

    $candidates = [Collections.Generic.List[string]]::new()
    if ($ExplicitPath) { $candidates.Add($ExplicitPath) }
    $preferred = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (!$candidates.Contains($preferred)) { $candidates.Add($preferred) }
    Get-Command aws -All -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Source -and !$candidates.Contains($_.Source)) { $candidates.Add($_.Source) }
    }

    foreach ($candidate in $candidates) {
        if (!(Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        try {
            $version = Invoke-NativeCommandResult `
                -FilePath $candidate `
                -ArgumentList @("--version") `
                -AllowedExitCodes @(0) `
                -Quiet
            if (($version.Output -join " ") -match '^aws-cli/2(?:\.|\s)') {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
        catch {
            continue
        }
    }
    throw "AWS CLI v2 was not found. Install it at C:\Program Files\Amazon\AWSCLIV2\aws.exe or pass -AwsCliPath."
}

function Invoke-CdkPathSafe {
    param(
        [Parameter(Mandatory = $true)][string]$InfraDirectory,
        [Parameter(Mandatory = $true)][string]$CdkVenv,
        [Parameter(Mandatory = $true)][string[]]$CdkArguments,
        [string]$AwsCliPath = "",
        [string]$Profile = ""
    )

    $scriptsDirectory = Join-Path $CdkVenv "Scripts"
    $python = Join-Path $scriptsDirectory "python.exe"
    if (!(Test-Path -LiteralPath $python -PathType Leaf)) {
        throw "CDK Python environment is missing: $python"
    }
    $previousPath = $env:PATH
    $awsEnvironmentNames = @(
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE"
    )
    $previousAwsEnvironment = @{}
    foreach ($name in $awsEnvironmentNames) {
        $previousAwsEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
    }
    Push-Location $InfraDirectory
    try {
        # cdk.json contains `python app.py`. Placing the venv first avoids a
        # quoted --app command string, which CDK splits incorrectly when the
        # repository path contains spaces.
        $env:PATH = "$scriptsDirectory;$previousPath"
        if ($Profile) {
            $aws = Get-AwsCliV2Path -ExplicitPath $AwsCliPath
            $export = Invoke-NativeCommandResult `
                -FilePath $aws `
                -ArgumentList @("configure", "export-credentials", "--profile", $Profile, "--format", "process") `
                -Quiet
            $credentials = ($export.Output -join [Environment]::NewLine) | ConvertFrom-Json
            if (!$credentials.AccessKeyId -or !$credentials.SecretAccessKey) {
                throw "AWS CLI did not export usable SDK credentials for profile $Profile."
            }
            [Environment]::SetEnvironmentVariable("AWS_ACCESS_KEY_ID", [string]$credentials.AccessKeyId, "Process")
            [Environment]::SetEnvironmentVariable("AWS_SECRET_ACCESS_KEY", [string]$credentials.SecretAccessKey, "Process")
            [Environment]::SetEnvironmentVariable("AWS_SESSION_TOKEN", [string]$credentials.SessionToken, "Process")
            # Keep the named profile on AWS CLI calls, but let CDK's SDK use
            # this short-lived process-only credential bridge.
            [Environment]::SetEnvironmentVariable("AWS_PROFILE", $null, "Process")
            [Environment]::SetEnvironmentVariable("AWS_DEFAULT_PROFILE", $null, "Process")
        }
        Invoke-NativeCommandResult `
            -FilePath "npx" `
            -ArgumentList (@("--yes", "aws-cdk@2.1140.0") + $CdkArguments) | Out-Null
    }
    finally {
        $env:PATH = $previousPath
        foreach ($name in $awsEnvironmentNames) {
            [Environment]::SetEnvironmentVariable($name, $previousAwsEnvironment[$name], "Process")
        }
        Pop-Location
    }
}

function Assert-CdkSynthEnvironment {
    param(
        [Parameter(Mandatory = $true)][string]$InfraDirectory,
        [Parameter(Mandatory = $true)][string]$StackName,
        [Parameter(Mandatory = $true)][string]$Account,
        [Parameter(Mandatory = $true)][string]$Region
    )
    $manifestPath = Join-Path $InfraDirectory "cdk.out\manifest.json"
    if (!(Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "CDK manifest is missing: $manifestPath" }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $property = $manifest.artifacts.psobject.Properties[$StackName]
    $artifact = if ($property) { $property.Value } else { $null }
    $expected = "aws://$Account/$Region"
    if ($null -eq $artifact -or [string]$artifact.environment -ne $expected) {
        throw "CDK synthesized the wrong environment. Expected $expected; found $([string]$artifact.environment)."
    }
}
