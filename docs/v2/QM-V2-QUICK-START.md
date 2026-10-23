# QuakeMesh V2 review quick start

Use this page immediately before and during the academic demonstration. QuakeMesh is an experimental simulation and corroboration prototype, not an official warning system.

## Before review day — run once

Requirements: Windows PowerShell, Git, Python 3.10+ (3.12 recommended), Node.js 20+, Java 17, Android SDK/ADB, AWS CLI v2, authenticated profile `quakemesh-demo`, Firebase `android/app/google-services.json`, and the reusable SNS application `QuakeMesh-FCM-Demo` in `ap-south-1`.

```powershell
Set-Location -LiteralPath 'C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh'
Set-ExecutionPolicy -Scope Process Bypass
aws sts get-caller-identity --profile quakemesh-demo --region ap-south-1
.\scripts\setup.ps1
.\PREPARE_QUAKEMESH_REVIEW.cmd
```

Success ends with `QUAKEMESH REVIEW PREPARATION PASSED` and `No QuakeMesh demo session was deployed.` PREPARE performs validation and may bootstrap the shared `CDKToolkit`; it does not create a QuakeMesh session stack.

## Start the demonstration

1. Connect one authorized Android phone by USB, unlock it, and accept the debugging prompt.
2. Confirm `adb devices -l` lists exactly one device.
3. Run:

```powershell
.\START_QUAKEMESH_REVIEW.cmd
```

Success ends with `QUAKEMESH REVIEW ENVIRONMENT READY`, `Smoke: PASS`, and `Distributed warm-up: PASS`. START creates or reuses one billable, session-owned AWS stack and starts:

- Local dashboard: `http://127.0.0.1:8080`
- AWS dashboard: `http://127.0.0.1:8081`
- Local API: `http://127.0.0.1:8000`

The current APK is installed automatically when exactly one authorized phone is connected.

## Prepare the phone

1. Open **QuakeMesh**. If needed:

   ```powershell
   adb shell am start -n com.quakemesh.app/.MainActivity
   ```

2. Grant location and notification permission.
3. Tap **Enable / disable simulated-drill alerts** until the status says `OPTED IN`.
4. Tap **Open urgent-alert permission settings** and allow full-screen urgent alerts when Android offers the setting.
5. Tap **Start monitoring**.
6. Wait for `API state: Connected`, a recent **Latest heartbeat**, and an H3 cell in **Location state**.
7. In the AWS dashboard, confirm the physical device appears under **Devices** with **Drill opt-in: Enabled**.
8. Disconnect USB and run `adb devices -l`. The list must be empty. Keep Wi-Fi/mobile data enabled.

## Run the wireless scenario

1. Open `http://127.0.0.1:8081` → **Scenario Lab**.
2. Select **Distributed corroboration**.
3. Keep `devices = 25` unless the review requires another validated value.
4. Press **Start** once.
5. Watch **Live run**, **Gate evaluation**, **Stage timeline**, and **Map evolution**.
6. Confirm the result becomes `CONFIRMATION` and the map shows a Detection Footprint and Warning Frontier.
7. On an unlocked phone, expect a heads-up notification; tap it to open the warning. On a locked/screen-off phone with permission allowed, the warning may open full-screen over the keyguard.
8. Tap **STOP ALERT SOUND**, then **ACKNOWLEDGE / DISMISS**.
9. In **Alerts**, confirm the physical-phone alert becomes `ACKNOWLEDGED`.

Unlocked heads-up behavior is not described as automatic full-screen takeover. The full warning opens after the user taps the notification; locked-screen presentation uses the permitted full-screen intent.

## Status and cleanup

Read-only status:

```powershell
.\STATUS_QUAKEMESH_REVIEW.cmd
```

Always stop after the review, including after a failed START:

```powershell
.\STOP_QUAKEMESH_REVIEW.cmd
```

Do not close the cleanup window until it prints:

```text
CLEAN: no known QuakeMesh session-owned AWS application resources remain.
```

`CDKToolkit` and the reusable SNS platform application remain by design. If STOP reports `INCOMPLETE`, do not delete resources manually: retain the error, run STATUS, and rerun STOP using the same profile/region.

For setup details and troubleshooting, use [QM-V2-COMPLETE-USER-GUIDE.md](QM-V2-COMPLETE-USER-GUIDE.md). For a printable sequence, use [QM-V2-REVIEW-DAY-CHECKLIST.md](QM-V2-REVIEW-DAY-CHECKLIST.md).
