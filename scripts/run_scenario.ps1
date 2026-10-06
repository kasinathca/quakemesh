param(
    [ValidateSet("isolated", "same-cell", "distributed", "degraded")]
    [string]$Scenario = "distributed",
    [int]$Devices = 25,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [int]$Seed = 42,
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
$base = $BaseUrl.TrimEnd("/")
$payload = @{
    scenario = $Scenario
    source = "cli"
    devices = $Devices
    seed = $Seed
    parameters = @{}
} | ConvertTo-Json -Depth 5

try {
    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "$base/v1/demo/scenario-runs" `
        -ContentType "application/json" `
        -Body $payload
}
catch {
    $detail = $_.ErrorDetails.Message
    if ($detail) {
        throw "Scenario start failed: $detail"
    }
    throw
}

$runId = $response.data.run_id
if (!$runId) {
    throw "Scenario control API did not return an authoritative run ID."
}
Write-Host "Authoritative scenario run: $runId" -ForegroundColor Cyan

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Milliseconds 500
    $snapshot = Invoke-RestMethod -Method Get -Uri "$base/v1/scenario-runs/$runId"
    $run = $snapshot.data
    Write-Progress `
        -Activity "QuakeMesh scenario $Scenario" `
        -Status $run.status
    if ($run.status -in @("COMPLETED", "FAILED")) {
        break
    }
} while ((Get-Date) -lt $deadline)

Write-Progress -Activity "QuakeMesh scenario $Scenario" -Completed
if ($run.status -notin @("COMPLETED", "FAILED")) {
    throw "Scenario run $runId did not finish within $TimeoutSeconds seconds."
}
$run | ConvertTo-Json -Depth 12
if ($run.status -ne "COMPLETED") {
    exit 1
}
