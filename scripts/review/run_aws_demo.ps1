$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "common.ps1")
$state = Read-ReviewState
if (!$state -or $state.status -ne "READY") { throw "Start the QuakeMesh review environment first." }
& (Join-Path $script:ReviewRoot "aws\scripts\run_aws_scenario.ps1") -SessionId $state.session_id -Scenario distributed -Devices 25
if ($LASTEXITCODE -ne 0) { throw "AWS distributed scenario failed." }
& (Join-Path $script:ReviewRoot ".venv\Scripts\python.exe") aws/scripts/verify_warmup.py --config $state.runtime_config --minimum-devices 4 --timeout-seconds 120
if ($LASTEXITCODE -ne 0) { throw "AWS distributed result verification failed." }
