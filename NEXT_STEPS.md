# QuakeMesh next steps

The V2 local control-plane phase is complete on the current Windows host. Do not interpret this as Android V2, AWS session, AWS deployment, or FCM verification.

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

## Next engineering phase (not performed here)

1. Define the Android V2 client against the frozen local V2 contracts, including physical provenance and ACK identity behavior.
2. Build and test Android on an emulator and physical device without weakening detector thresholds.
3. Replace the legacy AWS layout with session-scoped ownership, TTL cleanup, strict teardown, and zero-resource verification.
4. Implement AWS API/telemetry adapters that match the V2 envelopes and provenance rules.
5. Deploy only after explicit authorization and credential/account verification.
6. Validate live IoT, DynamoDB, event/alert parity, then opt-in FCM delivery.

Keep the following explicitly separate in reports: local verification, Android build/device verification, AWS synthesis, AWS live deployment, and FCM delivery. None implies another.
