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
4. Replace the legacy AWS layout with session-scoped ownership, TTL cleanup, strict teardown, and zero-resource verification.
5. Implement AWS API/telemetry adapters that match the V2 envelopes and provenance rules.
6. Deploy only after explicit authorization and credential/account verification.
7. Validate live IoT, DynamoDB, event/alert parity, then opt-in FCM delivery.

Keep the following explicitly separate in reports: local verification, Android build/device verification, AWS synthesis, AWS live deployment, and FCM delivery. None implies another.
