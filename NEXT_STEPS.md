# QuakeMesh next steps

The V2 local control-plane phase is complete on the current Windows host. The Android V2 API/domain foundation, monitoring interface, local-emulator configuration, alert identity, and ACK client compile into a debug APK and pass Android lint. A Windows review harness now prepares, starts, recovers, reports, and exactly stops local/AWS sessions; its preparation gate and CDK bootstrap passed in the intended account. The live session repetition matrix is still pending explicit mutation approval, so AWS deployment and CLEAN teardown are not yet claimed.

## Reproduce the local evidence

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\validate.ps1
.\scripts\demo_local.ps1 -Scenario distributed -Devices 25
```

Or start components separately:

```powershell
.\scripts\run_local.ps1
.\scripts\run_dashboard.ps1 -Port 8080
.\scripts\run_scenario.ps1 -Scenario isolated
.\scripts\run_scenario.ps1 -Scenario same-cell
.\scripts\run_scenario.ps1 -Scenario distributed
.\scripts\run_scenario.ps1 -Scenario degraded
```

The PowerShell runner now calls the scenario-control API and polls its authoritative run ID. The dashboard is at `http://127.0.0.1:8080`. Evidence exports are under `artifacts/session_exports/local/<run_id>/`; browser screenshots are under `artifacts/e2e/`.

## Next engineering steps

1. Run the Android debug APK on an emulator against local FastAPI at `http://10.0.2.2:8000`; verify heartbeat, trigger, physical provenance, alert polling, and idempotent ACK in SQLite/API views.
2. Repeat sensor/location monitoring on a physical device using a reachable HTTPS endpoint; record permission and lifecycle evidence.
3. Add Android instrumentation/accessibility coverage; focused V2 envelope/error/alert JVM tests are now present.
4. Execute the required first/fresh/idempotent START→STOP matrix with `START_QUAKEMESH_REVIEW.cmd` and `STOP_QUAKEMESH_REVIEW.cmd`; retain each sanitized CLEAN report.
5. Inspect live API Gateway/Lambda/DynamoDB/CloudWatch/IoT behavior and compare authoritative AWS correlation with Local V2.
6. Verify the AWS dashboard's live device/event/alert/ACK data path during that session.
7. Separately validate automatic expiry cleanup; manual exact-session STOP remains primary.
8. Configure and validate opt-in FCM delivery only after core cloud traffic is proven.

Keep the following explicitly separate in reports: local verification, Android build/device verification, AWS synthesis, AWS live deployment, and FCM delivery. None implies another.
