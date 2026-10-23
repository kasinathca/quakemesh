# QuakeMesh V2 complete user guide

## 1. Purpose and safety boundary

QuakeMesh V2 is an academic prototype that tests whether multiple geographically diverse smartphone-like motion observations satisfy configurable cloud corroboration rules. A QuakeMesh `CONFIRMATION` means those software rules passed. It is not an official earthquake declaration, does not estimate magnitude or epicentre, and is not validated for life-safety use.

The verified review flow is:

```text
Virtual phones
    → AWS IoT / Scenario Ingress
    → Ingress Lambda
    → DynamoDB evidence
    → H3 spatial-temporal corroboration
    → Confirmed event
    → Alert Dispatcher
    → Amazon SNS / Firebase Cloud Messaging
    → Opted-in physical Android phone
    → delivery receipts / acknowledgement
```

The physical phone supplies the current coarse H3 reference and is an explicitly opted-in simulated-drill recipient. Separately identified virtual devices supply the isolated synthetic evidence. Synthetic evidence is never attributed to the physical phone.

## 2. Prerequisites

### Windows workstation

- Windows 10 or 11 with PowerShell and Git.
- Python 3.10 or newer; Python 3.12 is recommended because AWS Lambda uses Python 3.12.
- Node.js 20 or newer and npm. Node.js 22 LTS is recommended for AWS/CDK work.
- Java 17.
- Android SDK/API 37, platform tools, and `adb` on `PATH`.
- An internet connection for AWS, npm/Gradle dependencies, map tiles, and FCM.

Confirm the tools:

```powershell
python --version
node --version
npm --version
java -version
adb version
git --version
```

### AWS

- AWS CLI v2, not the older v1 client.
- Authenticated profile `quakemesh-demo` with access to account `101541767123`.
- Region `ap-south-1` (Mumbai).
- A non-root identity. The review scripts reject the root identity.
- Shared CDK bootstrap stack `CDKToolkit`. PREPARE can create it with `-Bootstrap` through the wrapper.
- Reusable SNS FCM platform application named `QuakeMesh-FCM-Demo` in the same account and region.

Authenticate according to the profile type:

```powershell
# Static/role credentials configured for the profile
aws configure --profile quakemesh-demo

# Or, for an existing AWS SSO profile
aws sso login --profile quakemesh-demo

aws sts get-caller-identity --profile quakemesh-demo --region ap-south-1
```

Expected identity account: `101541767123`. Stop if another account is returned.

### Firebase and Android phone

- Firebase project configured for Android application ID `com.quakemesh.app`.
- Firebase configuration at `android/app/google-services.json`.
- SNS platform application configured with the Firebase Cloud Messaging HTTP v1 credentials.
- Android 8.0/API 26 or newer; the verified handset was a Motorola Edge 40 Neo running Android 15.
- USB debugging enabled for the initial installation.
- Location enabled, notification permission granted, and internet access available.
- Full-screen urgent-alert permission enabled when Android exposes it. If it is unavailable, the application reports that urgent heads-up fallback will be used.

Never commit `google-services.json`, `android/local.properties`, API keys, FCM tokens, runtime configuration, certificates, or device evidence. Repository rules ignore these files.

## 3. One-time preparation

Open PowerShell and use `-LiteralPath` because the repository path contains spaces:

```powershell
Set-Location -LiteralPath 'C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh'
Set-ExecutionPolicy -Scope Process Bypass
```

Create/install the local dependencies:

```powershell
.\scripts\setup.ps1
```

Then run the review preparation wrapper:

```powershell
.\PREPARE_QUAKEMESH_REVIEW.cmd
```

PREPARE:

- verifies the Git branch;
- resolves AWS CLI v2 and the authenticated non-root identity;
- runs the Python, schema, secret, PowerShell, dashboard, and browser validation gates;
- runs Android unit tests, APK assembly, and lint;
- builds the Linux-compatible H3 Lambda layer;
- synthesizes the CDK stack;
- creates `CDKToolkit` only when absent and bootstrap was requested by the wrapper;
- writes ignored readiness metadata under `artifacts/review/`.

Success ends with:

```text
QUAKEMESH REVIEW PREPARATION PASSED
No QuakeMesh demo session was deployed.
```

PREPARE does not create a QuakeMesh demo stack, but the shared CDK bootstrap can retain storage and generate small charges.

If preparation reports `Python environment missing. Run scripts/setup.ps1 first.`, run setup from the repository root. If it reports `Required command is missing`, install/fix the named tool and open a new terminal so `PATH` is refreshed.

## 4. Starting QuakeMesh

### What START does

Run:

```powershell
.\START_QUAKEMESH_REVIEW.cmd
```

START safely creates or reuses one exact-session AWS stack. It refuses ambiguous multiple stacks, an unexpected account/region, a near-expiry session, unrelated processes on required ports, and a mismatched SNS application ARN. It also:

- starts the local API on port 8000;
- starts the Local V2 dashboard on port 8080;
- deploys/reuses the session-owned AWS stack;
- verifies DynamoDB stream readiness;
- runs an HTTPS ingress smoke test;
- provisions session-owned virtual-phone IoT identities;
- runs and verifies a distributed warm-up;
- starts the AWS V2 dashboard on port 8081;
- writes the current AWS API URL/key into ignored Android build configuration;
- builds the current debug APK;
- installs the APK when exactly one authorized ADB device is present.

Success looks like:

```text
QUAKEMESH REVIEW ENVIRONMENT READY
Local V2: http://127.0.0.1:8080
AWS V2:   http://127.0.0.1:8081
Smoke: PASS | Distributed warm-up: PASS | Expiry fail-safe: ARMED
```

START creates billable AWS resources. The default session duration is 180 minutes, but automatic expiry is only a backstop; manual STOP is required.

### Read-only status

At any time run:

```powershell
.\STATUS_QUAKEMESH_REVIEW.cmd
```

STATUS does not deploy or delete anything. It shows local ports/owned processes, AWS identity, owned stacks, health and record counts, IoT Things, APK/ADB state, Android build target, and the last teardown result.

## 5. Installing and starting the Android application

START installs automatically when exactly one authorized phone is connected. The manual process is useful for diagnosis:

1. Connect the unlocked phone by USB.
2. Accept the **Allow USB debugging** prompt.
3. Verify:

   ```powershell
   adb devices -l
   ```

   Exactly one row should end in `device`. `unauthorized` means the prompt was not accepted; `offline` means reconnect/restart ADB.

4. Build and install if necessary:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh\android'
   .\gradlew.bat assembleDebug --no-daemon
   adb install -r '.\app\build\outputs\apk\debug\app-debug.apk'
   Set-Location -LiteralPath 'C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh'
   ```

   Expected install output ends in `Success`.

5. Launch QuakeMesh from the launcher, or:

   ```powershell
   adb shell am start -n com.quakemesh.app/.MainActivity
   ```

6. Grant precise/fine location and notification permission.
7. Tap **Enable / disable simulated-drill alerts** until **Simulated-drill alerts** says `OPTED IN — phone may receive labeled simulation drills`.
8. Tap **Open urgent-alert permission settings**. Allow full-screen alerts if Android presents the option. Return to QuakeMesh and confirm **Full-screen permission** says `Allowed`; otherwise the app truthfully reports the heads-up fallback.
9. Tap **Start monitoring**.
10. Confirm:

    - **Status** = `Active`;
    - **API state** = `Connected` plus a request identifier;
    - **Sensor state** = `Accelerometer monitoring active`;
    - **Location state** includes a current H3 cell;
    - **Latest heartbeat** is recent.

11. Open the AWS dashboard **Devices** page. Confirm the physical device is `Physical`, online/active, has a coarse H3 cell, and shows **Drill opt-in: Enabled**.
12. Disconnect USB.
13. Run `adb devices -l`; it must be empty. This confirms subsequent receipts cannot travel over ADB. Wi-Fi or mobile data must remain available.

The app sends a heartbeat every 30 seconds while monitoring. Wait one interval after a token, permission, or network change before diagnosing registration.

## 6. Dashboard guide

### Local dashboard — `http://127.0.0.1:8080`

This connects to FastAPI/SQLite and is best for explaining the control-plane contract, detector settings, local evidence export, and reproducible scenarios without cloud charges.

### AWS dashboard — `http://127.0.0.1:8081`

This connects to the deployed API Gateway/Lambda/DynamoDB system. Scenario controls and run telemetry are real cloud operations. The environment header reads `AWS V2 Demo · ap-south-1`.

### Implemented pages

| Page | What it shows or does |
|---|---|
| Overview | API mode/health, active run, device/evidence/event/alert counts, current experiment, and latest event. |
| Live Map | Physical and virtual device markers, latest event Detection Footprint, Warning Frontier, and an H3 inventory if map tiles are unavailable. |
| Scenario Lab | Five scenarios, validated parameters, Start/Reset, run verdict, gate evaluation, ordered stage timeline, map evolution, and structured logs. Local mode can export run evidence; AWS retains cloud evidence instead. |
| Events | Confirmed/resolved events, provenance, run identity, devices/evidence, lifecycle, Detection Footprint, Warning Frontier, and related alert count. |
| Devices | Safe registry fields—never raw FCM tokens/SNS endpoint ARNs—plus physical/virtual type, H3 cell, online state, opt-in state, and controlled-test tool in AWS mode. |
| Alerts | Alert target/delivery/acknowledgement state, transport, timestamps, failures, and manual dashboard acknowledgement. `TARGETED` alone does not prove phone receipt. |
| Experiments | Scenario run history, expected/observed result, source, device count, seed, and run selection. |
| Evaluation / Metrics | Tracked historical 48-trial and challenging 320-trial datasets, filters, confusion matrices, metrics, trial records, and exports. These are offline evaluation artifacts. |
| Infrastructure | Runtime mode/version, environment, region, session, API connectivity, scenario-control availability, and local detector configuration. AWS detector configuration is not exposed by the read API. |
| Session | Local/AWS mode, session ID, region, active run, start time, and AWS expiry. |

The top-right connection badge must say `connected`. If it says `disconnected`, the last verified snapshot remains visible while the client retries; do not treat it as live data.

## 7. Simulating an earthquake near the physical phone

1. Complete the phone registration/monitoring procedure above.
2. Open `http://127.0.0.1:8081` and select **Scenario Lab**.
3. Select **Distributed corroboration**. Its expected result is `CONFIRMATION`.
4. Use `devices = 25`, `seed = 42`, and the displayed default propagation interval unless demonstrating a planned variation.
5. Press **Start** once. A second active run is intentionally rejected.
6. Watch the stage timeline as virtual devices register and evidence is accepted.
7. In **Gate evaluation**, verify recent evidence, distinct-device diversity, distinct H3-cell diversity, and spatial coherence pass.
8. In **Map evolution** or **Live Map**, distinguish the physical phone marker from virtual devices. The phone is the reference/recipient; it is not one of the virtual evidence sources.
9. Explain:

   - **Detection Footprint** = coarse H3 cells that contributed to the confirmed component.
   - **Warning Frontier** = the configured H3 ring around the footprint for demonstration targeting. It is not a seismic wavefront or predicted arrival-time boundary.

10. Wait for **Status: COMPLETED**, **Observed: CONFIRMATION**, and **EXPECTED RESULT OBSERVED**.
11. Receive the Android alert wirelessly.
12. On an unlocked home screen, expect a heads-up notification with warning sound/spoken message. Tap it to open the warning activity. Do not describe this as automatic unlocked-screen takeover.
13. On a locked/screen-off phone with full-screen permission, the warning can wake the screen and appear over the keyguard.
14. Tap **STOP ALERT SOUND**. This stops current sound/TTS/vibration attention output but does not acknowledge the cloud alert.
15. Tap **ACKNOWLEDGE / DISMISS**. This stops attention output, posts the authoritative acknowledgement, and closes the warning.
16. In dashboard **Alerts**, confirm the phone's alert status becomes `ACKNOWLEDGED` with an acknowledgement timestamp.

Use Scenario Lab **Reset** only after the active run finishes. In AWS mode this clears the dashboard's selected run while retaining cloud evidence; it is not resource teardown.

## 8. Alternative scenarios

All parameter controls are validated server-side. Unsupported, mistyped, conflicting, or out-of-range values are rejected.

| Scenario | Parameters | Expected result | Interpretation |
|---|---|---|---|
| Isolated disturbance | `devices` 4–500; `seed` 0–2147483647 | `NO_CONFIRMATION` | Only one device triggers. A single phone cannot satisfy distinct-device quorum. |
| Same-cell cluster | `devices`; `seed`; propagation 0–1000 ms | `NO_CONFIRMATION` | Several devices may trigger, but they occupy one coarse H3 cell and fail spatial diversity. |
| Distributed corroboration | `devices`; `seed`; propagation 0–1000 ms | `CONFIRMATION` | Multiple devices distributed across coherent H3 cells satisfy the positive path. |
| Degraded network | `devices`; `seed`; loss 0–0.95; jitter 0–5000 ms; propagation 0–1000 ms | `CONDITIONAL` | Confirmation depends on enough timely, diverse evidence surviving loss and delay. Defaults are 25% loss and 900 ms maximum jitter. |
| False-positive demonstration | `devices`; `seed`; propagation 0–1000 ms | `NO_CONFIRMATION` | Ordinary/temporally uncorrelated or below-gate motion does not satisfy the complete quorum. |

Negative scenarios are successful when no event is confirmed and no authoritative phone drill is dispatched. Do not treat “no notification” as a system failure until the expected result is checked.

## 9. Android alert behavior

- **Heads-up notification:** the normal unlocked/background presentation. The user taps it to open details.
- **Full-screen warning activity:** dark-red `SIMULATED EARTHQUAKE` interface with event/alert identity, H3 warning area, corroborating-device/cell counts, and controls.
- **Locked-screen presentation:** with urgent-alert permission, `showWhenLocked`/`turnScreenOn` and full-screen intent allow presentation over the keyguard.
- **Audible alert and spoken warning:** the attention service requests alarm-stream audio focus, loops the bundled warning tone, and speaks the warning. The service has a bounded duration.
- **STOP ALERT SOUND:** stops attention output only. The alert remains unacknowledged.
- **ACKNOWLEDGE / DISMISS:** stops attention output and sends the authoritative Android acknowledgement before closing.
- **Dismiss:** stops attention output and closes the screen without claiming acknowledgement.
- **Duplicate suppression:** cloud dispatch uses stable alert identity and retry-safe state; Android persists the same alert ID and suppresses repeat presentation.

The application does not silently change ringer or Do Not Disturb settings. Silent-mode/DND bypass and vibration-strength investigation are outside the final review scope.

## 10. Local versus AWS operation

| Capability | Local V2 | AWS V2 |
|---|---|---|
| API/storage | FastAPI + SQLite | API Gateway + Lambda + DynamoDB |
| Virtual scenarios | Yes | Yes, through real deployed scenario ingress/processing |
| H3 corroboration | Production shared detector | Production shared detector in Lambda |
| Scenario telemetry/history | Yes | Yes |
| Evidence export | Writes local JSON | Not exposed; cloud evidence remains in session tables |
| Reset | Transactional scenario-data reset | Clears dashboard selection; retained evidence remains |
| Physical Android heartbeat | Emulator/host development path | Verified HTTPS heartbeat and H3 registration |
| SNS/FCM wireless notification | No SNS/FCM | Yes, requires Firebase/SNS and phone opt-in |
| Cloud acknowledgement | No cloud resource | Verified Android → API → DynamoDB state |
| AWS charges | None | Yes; START creates managed/serverless resources |
| Session expiry | Not applicable | Metadata/backstop only; manual STOP is mandatory |

Offline evaluation pages work without creating AWS resources. START, AWS scenarios, API calls, IoT traffic, Lambda, DynamoDB, CloudWatch, SNS, and bootstrap storage can consume cloud resources.

## 11. Stopping and cleanup

Always run STOP after the presentation, after a failed START, or whenever session state is uncertain:

```powershell
Set-Location -LiteralPath 'C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh'
.\STOP_QUAKEMESH_REVIEW.cmd
```

STOP:

- stops only local PID/command pairs owned by the review harness;
- restores the previous Android `local.properties` configuration;
- deletes exact-session simulator Things/certificates;
- deletes exact marker-owned SNS endpoints before and after stack destruction;
- destroys the exact tagged session stack;
- verifies the captured concrete resource inventory;
- removes ignored live-session metadata only after verification.

Success is exactly:

```text
CLEAN: no known QuakeMesh session-owned AWS application resources remain.
```

Shared `CDKToolkit`, its content-addressed assets, and the reusable SNS platform application remain. CLEAN means no known session-owned QuakeMesh application resource remains; it does not mean the account is empty or prior charges are reversed.

If STOP says `INCOMPLETE`, preserve `artifacts/review/last-teardown.json` and the displayed error. Run STATUS and rerun STOP with the same profile/region. Do not manually delete broadly named resources and do not run `git clean -fdx`.

## 12. Troubleshooting

### AWS login expired or wrong identity

Symptoms include expired-token errors, `Unable to locate credentials`, or the wrong account from STS.

```powershell
aws sso login --profile quakemesh-demo
aws sts get-caller-identity --profile quakemesh-demo --region ap-south-1
```

Do not continue unless account `101541767123` and a non-root identity are shown.

### Wrong AWS CLI installation

Run `aws --version`; it must report `aws-cli/2`. PREPARE/START use the repository's resolver and fail rather than silently using an incompatible CLI. Remove an AWS CLI v1 path conflict or pass the supported `-AwsCliPath` parameter directly to the underlying PowerShell script.

### Missing Python, Node, or Java dependencies

- `Python environment missing. Run scripts/setup.ps1 first.` → run `.\scripts\setup.ps1`.
- `Required command is missing: node/npm/npx/java` → install it, reopen PowerShell, and verify the version commands.
- Gradle errors about Java → set Android Studio/terminal to JDK 17.

### Phone not detected by ADB

```powershell
adb kill-server
adb start-server
adb devices -l
```

Reconnect the cable, unlock the phone, select file-transfer mode if required, and accept the RSA prompt. START installs automatically only when exactly one authorized device is present; multiple devices produce `MULTIPLE DEVICES - MANUAL SELECTION`.

### Firebase configuration missing

If `android/app/google-services.json` is absent, the APK builds without Firebase activation and wireless FCM cannot work. Follow `docs/FIREBASE_SNS_SETUP.md`, use the correct package `com.quakemesh.app`, then rebuild/reinstall. Never paste the service credential or FCM token into tracked files.

### Android app shows the wrong environment

The review harness temporarily writes the active AWS API URL/key into ignored `android/local.properties` and creates an Android marker. Run START while the phone is connected, reinstall the APK, and verify **Environment** in the app. STOP restores the prior local configuration.

### Heartbeat failing

Check location permission, location services, monitoring status, internet access, and the app's **API state** error. Run STATUS to verify the AWS API health. A heartbeat occurs every 30 seconds; wait one cycle after correcting configuration.

### Phone absent from the device registry or H3 missing

The phone must be monitoring with precise location available. Wait for a successful heartbeat, then refresh the AWS **Devices** page. If **Location state** says unavailable, enable location and grant fine location permission before restarting monitoring.

### No simulated event confirmation

Check the selected scenario's expected result first. Isolated, same-cell, and false-positive runs should not confirm. For distributed, inspect Gate evaluation for motion, recency, device diversity, spatial diversity, and coherence failures. Use the default parameters and ensure no other run is active.

### Scenario already running

The system enforces one `QUEUED`/`RUNNING` scenario. Wait for `COMPLETED` or `FAILED`. Reset is deliberately disabled while a run is active.

### Alert not received

Verify all of the following:

- physical device is online in **Devices**;
- drill opt-in is `Enabled`;
- notification permission is granted;
- Firebase file and reusable SNS application are configured;
- phone has internet after USB removal;
- scenario actually reached `CONFIRMATION`;
- an alert row exists for the physical device;
- notification channel is not disabled in Android settings.

Do not use ADB connectivity as proof of wireless delivery; the verified procedure requires `adb devices -l` to be empty before the trigger.

### Dashboard disconnected

The banner says `API disconnected. The last verified snapshot remains visible while recovery continues.` Run STATUS. Confirm the correct port is listening and that START did not report `Port 8000/8080/8081 is occupied by a process not owned by this review state.` Do not kill unrelated processes automatically.

### Full-screen permission unavailable

Use **Open urgent-alert permission settings** in the app. On Android 14+, allow full-screen intent if the OS presents the control. When not allowed, QuakeMesh reports `Not allowed — urgent heads-up fallback will be used`. Continue with the heads-up path and describe the limitation truthfully.

### Failed cleanup

If the wrapper says `STOP IS INCOMPLETE. Do not assume AWS resources are clean.`, keep the terminal output and ignored report. Re-authenticate the same profile, run STATUS, and rerun STOP. The teardown is idempotent and exact-session guarded. Do not remove `CDKToolkit` or the shared SNS application.

## 13. Review-day sequence

Use the printable [QM-V2-REVIEW-DAY-CHECKLIST.md](QM-V2-REVIEW-DAY-CHECKLIST.md). The minimum sequence is:

```text
PREPARE → connect phone → START → register/opt in → unplug USB
→ run distributed scenario → stop sound → acknowledge
→ show positive/negative/evaluation evidence → STOP → require CLEAN
```

## 14. Evidence and further reading

- [Final live validation](QM-V2-FINAL-DEMO-VALIDATION.md)
- [Academic review content package](QM-V2-ACADEMIC-REVIEW-PACKAGE.md)
- [Architecture](QM-V2-ARCHITECTURE.md)
- [API contract](QM-V2-API-CONTRACT.md)
- [Research evaluation](QM-V2-RESEARCH-EVALUATION.md)
- [Firebase/SNS setup](../FIREBASE_SNS_SETUP.md)
- [Final review verification](QM-V2-FINAL-REVIEW-VERIFICATION.md)
