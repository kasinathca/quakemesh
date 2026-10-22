# QuakeMesh next steps

QuakeMesh V2 is complete as an academic prototype on the current Windows host. Local, dashboard, Android, AWS pipeline, controlled FCM, and deterministic synthetic-evaluation evidence are recorded. Session `qm-20261019-112257-b77a` ended with an independently repeated `CLEAN` audit: zero active QuakeMesh stacks, no active review state, no session-owned SNS endpoint, and ports 8000/8080/8081 stopped. Shared `CDKToolkit` and the reusable enabled SNS platform application remain intentionally retained.

## Reproduce the local evidence

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\validate.ps1
.\.venv\Scripts\python.exe scripts\run_evaluation.py --output artifacts\evaluation\latest --trials-per-scenario 12 --base-seed 20261019 --publish-dashboard
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

1. Diagnose and separately validate the automatic-expiry path. The scheduled cleanup did not complete on time in the successful session; do not weaken the exact-session ownership guards, and retain manual STOP as primary until fixed and reverified.
2. Add Android instrumentation, TalkBack/accessibility, process-recreation, and broader device-matrix coverage. The Motorola Android 15 device did not show an automatic heads-up overlay; full-screen intent remains intentionally disabled.
3. Exercise an authoritative alert ACK from the physical handset and the AWS dashboard in a future explicitly approved live session. The controlled direct FCM test correctly created no authoritative ACK record.
4. Run the new controlled-notification API in an explicitly approved AWS session and verify `SNS_ACCEPTED → FCM_RECEIVED → NOTIFICATION_POSTED → OPENED` with USB disconnected. The implementation is locally validated, but this revised flow has not yet been exercised live.
5. Re-run automatic expiry with the expanded 600 s cleanup budget and retain Scheduler/Lambda evidence. The timeout change is an offline hardening, not proof that scheduled expiry is repaired.
6. Obtain appropriately licensed raw earthquake handset waveforms before making any real-world sensitivity claim. The integrated UCI HAR evaluation covers authentic human-activity negatives only; public MyShake parametric data is not a raw triaxial substitute.
7. Measure performance, concurrency, cloud latency and cost under a separately approved load plan; the present new evidence remains offline/local.

Keep local verification, controlled synthetic evaluation, Android device behavior, AWS live processing, FCM receipt, and real-world seismological validity separate in every report. None implies another.
