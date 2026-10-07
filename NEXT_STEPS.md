# QuakeMesh next steps

The V2 local control-plane phase is complete on the current Windows host. The Android V2 API/domain foundation, monitoring interface, local-emulator configuration, alert identity, and ACK client compile into a debug APK and pass Android lint. Emulator/physical-device behavior, AWS V2, and live FCM are still separate verification scopes.

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
3. Add focused Android parser/state unit tests and instrumentation/accessibility coverage.
4. Install/configure AWS CLI, verify the intended account/region, and deploy the synthesized session-scoped V2 stack.
5. Run the AWS heartbeat/trigger smoke script, inspect API Gateway/Lambda/DynamoDB/CloudWatch, then run an IoT distributed scenario and compare correlation behavior with local V2.
6. Launch the implemented dashboard AWS mode with the deployed session config and verify real device/event/alert/ACK visibility.
7. Validate exact-session teardown and zero-owned-resource reporting, then add automatic expiry cleanup as a backstop.
8. Configure and validate opt-in FCM delivery only after core cloud traffic is proven.

Keep the following explicitly separate in reports: local verification, Android build/device verification, AWS synthesis, AWS live deployment, and FCM delivery. None implies another.
