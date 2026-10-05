param(
    [int]$Devices = 25,
    [ValidateSet("isolated","same-cell","distributed","degraded")]
    [string]$Scenario = "distributed",
    [int]$BackendPort = 8000,
    [int]$DashboardPort = 8080,
    [int]$StartupTimeoutSeconds = 20
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Py)) { throw "Run .\scripts\setup.ps1 first" }
. (Join-Path $PSScriptRoot "process_helpers.ps1")

function Test-HttpEndpoint {
    param([string]$Uri)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
    }
    catch {
        return $false
    }
}

$backendHealth = "http://127.0.0.1:$BackendPort/health"
$dashboardUrl = "http://127.0.0.1:$DashboardPort/"

if (Test-HttpEndpoint $backendHealth) {
    Write-Host "Backend already running at $backendHealth" -ForegroundColor DarkYellow
}
else {
    Write-Host "Starting QuakeMesh local backend..." -ForegroundColor Cyan
    Start-PowerShellScriptSafely -ScriptPath (Join-Path $Root "scripts\run_local.ps1") -WorkingDirectory $Root -NoExit | Out-Null
}

if (Test-HttpEndpoint $dashboardUrl) {
    Write-Host "Dashboard already running at $dashboardUrl" -ForegroundColor DarkYellow
}
else {
    Write-Host "Starting QuakeMesh dashboard..." -ForegroundColor Cyan
    Start-PowerShellScriptSafely -ScriptPath (Join-Path $Root "scripts\run_dashboard.ps1") -NamedArguments @{ Port = $DashboardPort } -WorkingDirectory $Root -NoExit | Out-Null
}

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
while ((Get-Date) -lt $deadline -and !(Test-HttpEndpoint $backendHealth)) {
    Start-Sleep -Milliseconds 400
}
if (!(Test-HttpEndpoint $backendHealth)) {
    throw "QuakeMesh backend did not become healthy within $StartupTimeoutSeconds seconds. Check the backend PowerShell window for the startup error."
}

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
while ((Get-Date) -lt $deadline -and !(Test-HttpEndpoint $dashboardUrl)) {
    Start-Sleep -Milliseconds 400
}
if (!(Test-HttpEndpoint $dashboardUrl)) {
    throw "Dashboard did not become reachable within $StartupTimeoutSeconds seconds. Check the dashboard PowerShell window for the startup error."
}

Write-Host "Backend healthy. Running scenario '$Scenario' with $Devices virtual devices..." -ForegroundColor Green
& (Join-Path $Root "scripts\run_scenario.ps1") -Scenario $Scenario -Devices $Devices -BaseUrl "http://127.0.0.1:$BackendPort"
if ($LASTEXITCODE -ne 0) { throw "Scenario runner failed with exit code $LASTEXITCODE" }

Write-Host "Open http://127.0.0.1:$DashboardPort" -ForegroundColor Green
Write-Host "Backend API: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
