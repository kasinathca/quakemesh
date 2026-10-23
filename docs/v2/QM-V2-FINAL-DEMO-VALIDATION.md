# QuakeMesh V2 final demo validation

Validation date: 2026-10-24 (Asia/Calcutta)

AWS region: `ap-south-1`

Ephemeral session: `qm-20261023-190030-20bc`

Physical device: Motorola Edge 40 Neo (`QM-ANDROID-5f786f75-a29`)
Safety label: `QUAKEMESH — SIMULATED EARTHQUAKE DRILL`

This report records observed integration behavior. QuakeMesh remains an experimental academic prototype and is not a life-safety warning system. No synthetic observation was represented as physical evidence; the phone was only the coarse geographic reference and explicitly opted-in drill recipient.

## End-to-end result

The AWS dashboard scenario path used the phone's current registered H3 cell, created distinct virtual devices around that cell, submitted their observations through the deployed ingress and production correlator, confirmed eligible events, and dispatched the confirmed simulation through AWS SNS and FCM to the registered physical handset. The Android client recorded cloud receipts and used stable alert IDs for deduplication.

The final wireless run was `aws-1792784008795-bc491bff`. Before it started, `adb devices -l` returned no devices. AWS observed 8 accepted virtual-device evidence records, produced one confirmed event, and the handset independently posted `FCM_RECEIVED`, `NOTIFICATION_POSTED`, `AUDIO_STARTED`, `OPENED`, and `AUDIO_STOPPED` receipts followed by an `ACKNOWLEDGED` state with source `android`. USB remained absent when the receipts were queried.

## Live scenario evidence

| Scenario | Run | Expected | Observed | Accepted evidence | Result |
|---|---|---|---|---:|---|
| Distributed, locked/screen off | `aws-1792783306059-be975359` | confirmation | confirmation | 8 | PASS |
| Isolated shaking | `aws-1792783386339-14a5f73c` | no confirmation | no confirmation | 1 | PASS |
| Same-cell movement | `aws-1792783394484-22b6a83b` | no confirmation | no confirmation | 6 | PASS |
| False-positive motion | `aws-1792783402421-796c469e` | no confirmation | no confirmation | 0 | PASS |
| Degraded, 25% loss / 900 ms jitter | `aws-1792783440982-6811f8c3` | conditional | confirmation | 12 | PASS |
| Distributed, total-silence DND | `aws-1792783532435-da437be3` | confirmation | confirmation | 8 | PASS for delivery; audible output not machine-verifiable |
| Distributed, USB unplugged | `aws-1792784008795-bc491bff` | confirmation | confirmation | 8 | PASS |

Replaying the final DND run's DynamoDB stream image left the existing physical alert at one delivery attempt and preserved its original receipt timestamps. No second FCM publish or warning was produced: PASS.

## Physical Android matrix

| Test | Evidence | Result |
|---|---|---|
| App open, screen on | `WarningActivity` became the resumed activity after real FCM delivery. | PASS |
| App background, screen on | High-importance notification with STOP ALERT action was visible over the launcher. | PASS |
| App not in foreground | FCM receipt and foreground attention-service audio receipt were persisted. | PASS |
| Phone locked / screen off | Device changed from dozing/screen-off to awake; keyguard remained showing and was occluded by `WarningActivity`. | PASS |
| Full-screen presentation | Dark-red `SIMULATED EARTHQUAKE` UI rendered over the locked keyguard; `canUseFullScreenIntent()` was allowed. | PASS |
| Normal sound | Alarm-category looping player requested exclusive transient audio focus; perceptual loudness requires human confirmation. | NOT VERIFIED perceptually |
| Silent ringer | With ringer mode temporarily silent, delivery and `AUDIO_STARTED` succeeded on the alarm stream; original mode was restored. | PASS for execution; NOT VERIFIED perceptually |
| Do Not Disturb | Under total-silence DND, delivery, notification posting and alarm-stream focus request succeeded; DND was restored to off. Channel DND bypass remained false because no special policy access was silently granted. | PASS for compliant behavior; NOT VERIFIED audible bypass |
| Vibration | Repeating waveform was configured and invoked; physical sensation requires human confirmation. | NOT VERIFIED perceptually |
| USB unplugged | ADB device list empty before trigger and after cloud receipts; SNS/FCM path completed. | PASS |
| Duplicate event | Stable cloud alert remained at `attempts=1`; Android also persists a stable per-alert dedupe key. | PASS |
| Negative scenarios | Isolated, same-cell, and below-motion-gate scenarios created no confirmed event and no drill alert. | PASS |
| Acknowledgement | Locked-screen run became `ACKNOWLEDGED` with source `android`; `AUDIO_STOPPED` was recorded. | PASS |

The app never changes ringer or DND settings. Test-only ADB changes were bounded and restored to baseline (`mode_ringer=2`, `zen_mode=0`).

## Automated regression evidence

- `scripts/validate.ps1`: 14 PASS, 3 documented environment-scope SKIP, 0 FAIL; 109 Python tests, Ruff, schemas, secret scan, launcher tests, TypeScript, ESLint, 7 Vitest tests, production build, 3 Playwright tests, and repository audit.
- Android: `testDebugUnitTest assembleDebug lintDebug` completed successfully.
- Final focused integration checks: 34 Python tests passed; Ruff passed.
- Dashboard final checks: ESLint passed, 7 Vitest tests passed, TypeScript production build passed. The only build diagnostic was the existing non-fatal bundle-size warning.
- CDK synthesis and three in-place updates of the owned test stack completed. One attempted update rolled back cleanly because an expiry value was accidentally localized; it was corrected by preserving the ISO-8601 value.

## Retained local evidence

Ignored device screenshots and replay payloads are retained under `artifacts/review/device-evidence/`. They contain no AWS credentials. Session runtime configuration remains ignored and must not be committed.

## Cleanup requirement

The session is evidence only until `scripts/review/stop.ps1` destroys the exact owned resources. The work is complete only after the teardown report says `CLEAN`; shared `CDKToolkit` and the reusable SNS platform application are intentionally retained.
