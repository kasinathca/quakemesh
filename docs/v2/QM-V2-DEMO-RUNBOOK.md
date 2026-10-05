# Demo runbook

## Local (target workflow)

```powershell
.\scripts\setup_windows.ps1
.\scripts\validate.ps1
.\scripts\demo_local.ps1 -Scenario distributed -Devices 25
```

Show the mode/connection banner, then isolated and same-cell gate failures followed by a distributed confirmation, footprint/frontier, alert records, and exported evidence. Do not show API keys, FCM tokens, private keys, `local.properties`, runtime config, or certificate files.

## AWS (only after setup and explicit start)

```powershell
aws sso login --profile quakemesh-demo
.\aws\scripts\session_preflight.ps1 -AwsProfile quakemesh-demo
.\aws\scripts\session_start.ps1 -AwsProfile quakemesh-demo -Region ap-south-1 -Devices 25 -TTLMinutes 120
.\aws\scripts\session_stop.ps1
```

Success requires a local cleanup report that finds zero session-owned resources. If status is `INCOMPLETE`, run `session_recover.ps1`; do not start another session over unknown state. These V2 commands are design targets until their traceability rows become verified.
