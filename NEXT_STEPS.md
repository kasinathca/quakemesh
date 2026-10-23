# QuakeMesh next steps

QuakeMesh V2 is complete for its academic demonstration on the current Windows host. Local and AWS Scenario Lab execution, the dashboard, Android heartbeat/H3 registration, USB-disconnected SNS/FCM delivery, locked-screen warning presentation, unlocked heads-up notification, audible/spoken warning, Stop Alert Sound, authoritative acknowledgement, deduplication, and synthetic research evaluation are recorded. Final session `qm-20261023-190030-20bc` ended `CLEAN`; a fresh read-only audit on 2026-10-24 again found zero live session-owned resources. Shared `CDKToolkit` and the reusable SNS platform application remain intentionally retained.

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

## Review-day next action

Follow [QM-V2-QUICK-START.md](docs/v2/QM-V2-QUICK-START.md), keep [QM-V2-REVIEW-DAY-CHECKLIST.md](docs/v2/QM-V2-REVIEW-DAY-CHECKLIST.md) open, and always finish with `STOP_QUAKEMESH_REVIEW.cmd`. Do not create a cloud session merely to inspect the repository or evaluation results.

## Future scope after the academic review

1. Diagnose and separately validate the automatic-expiry path. The scheduled cleanup did not complete on time in the successful session; do not weaken the exact-session ownership guards, and retain manual STOP as primary until fixed and reverified.
2. Add Android instrumentation, TalkBack/accessibility, process-recreation, and broader device-matrix coverage. The verified Motorola behavior must not be generalized to every Android device.
3. Re-run automatic expiry under a separately approved session and retain Scheduler/Lambda evidence. Manual guarded STOP is still primary.
4. Obtain appropriately licensed raw earthquake handset waveforms before making any real-world sensitivity claim. The integrated UCI HAR evaluation covers authentic human-activity negatives only.
5. Measure performance, concurrency, cloud latency and cost under a separately approved load plan.

Keep local verification, controlled synthetic evaluation, Android device behavior, AWS live processing, FCM receipt, and real-world seismological validity separate in every report. None implies another.
