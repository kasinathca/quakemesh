# QuakeMesh — Exact Next Steps on Your PC

The controlled V2 plan and current evidence are in `docs/v2/`. The highest-priority incomplete work is session-scoped AWS ownership/TTL cleanup, the Android Material 3/Demo Lab/ACK path, and the remaining dashboard views. Design documents are not implementation evidence.

Follow these in order. Do not begin with AWS or Android; first prove the shared/local implementation on your PC.

## Phase 1 — Extract and inspect

1. Extract the ZIP to a short path, for example:

   ```text
   C:\Users\kasin\Projects\QuakeMesh
   ```

2. Open **PowerShell** in that directory.

3. Confirm the expected files exist:

   ```powershell
   Get-ChildItem
   ```

   You should see `src`, `local_runtime`, `simulator`, `aws`, `android`, `dashboard`, `tests`, `docs`, `README.md`, and this file.

## Phase 2 — Install local prerequisites

Recommended:

- Python 3.12 x64;
- Git;
- current PowerShell/Windows;
- Node.js 22 LTS if you plan to deploy AWS;
- AWS CLI v2 if you plan to deploy AWS;
- Android Studio later.

Check Python:

```powershell
python --version
```

Use Python 3.12 if you have multiple installations.

## Phase 3 — Create the Python environment

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

This creates `.venv` and installs real H3 plus the pinned runtime/dev dependencies.

Then validate:

```powershell
.\scripts\validate.ps1
```

**Do not continue until there are zero failing tests.** The real-H3 test should run, not skip, after the dependency installation succeeds.

## Phase 4 — Run the complete local demonstration

Simplest path:

```powershell
.\scripts\demo_local.ps1 -Scenario distributed -Devices 25
```

It opens local runtime/dashboard PowerShell windows and runs the simulator.

Or run manually.

Terminal 1:

```powershell
.\scripts\run_local.ps1
```

Terminal 2:

```powershell
.\scripts\run_dashboard.ps1
```

Terminal 3:

```powershell
.\scripts\run_scenario.ps1 -Scenario isolated -Devices 25
.\scripts\run_scenario.ps1 -Scenario same-cell -Devices 25
.\scripts\run_scenario.ps1 -Scenario distributed -Devices 25
.\scripts\run_scenario.ps1 -Scenario degraded -Devices 25
```

Open:

```text
http://127.0.0.1:8080
```

Check that isolated and same-cell cases do not confirm while the distributed case normally does under default configuration.

## Phase 5 — Create the new Git repository

Follow **`NEW_REPO_SETUP_AND_PUSH.md`** exactly.

Do the secret scan before `git add`:

```powershell
.\.venv\Scripts\python.exe scripts\check_secrets.py
```

Do not commit certificates, `runtime-config.json`, Android `local.properties`, or Firebase `google-services.json`.

## Phase 6 — Configure AWS CLI

Sign into/configure the AWS account you want to use.

Typical check:

```powershell
aws sts get-caller-identity
```

The account/ARN printed here is the account where CDK will deploy.

Default project region is Mumbai:

```text
ap-south-1
```

## Phase 7 — Deploy AWS

From repository root:

```powershell
.\aws\scripts\deploy.ps1 -Region ap-south-1
```

The script will:

- build the Linux-compatible H3 Lambda layer;
- set up a dedicated CDK Python venv;
- synthesize with that exact interpreter;
- bootstrap/deploy the CDK stack;
- create the API key/usage plan;
- export API URL/key/IoT endpoint to `artifacts/runtime-config.json`.

If AWS asks about credentials/permissions, fix those rather than editing project code around the error.

## Phase 8 — Provision virtual AWS IoT phones

For 25 devices:

```powershell
.\aws\scripts\provision_simulators.ps1 -Count 25
```

This creates one Thing/certificate per virtual phone. Generated private keys are under `artifacts/` and are gitignored.

## Phase 9 — Run the AWS IoT end-to-end path

```powershell
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario isolated -Devices 25
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario same-cell -Devices 25
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario distributed -Devices 25
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario degraded -Devices 25
```

Inspect:

- DynamoDB DeviceState/Evidence/Events/AlertDelivery;
- CloudWatch Lambda logs and alarms;
- IoT Core MQTT test client if desired;
- local dashboard configured against AWS read API.

After deploy, `dashboard/config.aws.js` is generated. To use it, copy its contents into `dashboard/config.js` locally or change the script reference in `index.html`; keep account-specific files out of Git.

Archive an important run after it finishes:

```powershell
$trace = Get-ChildItem artifacts\traces\*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
.\aws\scripts\upload_trace.ps1 -Trace $trace.FullName -Region ap-south-1
```

The S3 uploader validates trace schema and records its SHA-256 in object metadata.

## Phase 10 — Add Firebase/SNS for Android alerts

Follow:

```text
docs/FIREBASE_SNS_SETUP.md
```

You must personally supply Firebase project credentials; the repository intentionally contains none.

Before a deploy/update with SNS FCM enabled:

```powershell
$env:QM_SNS_PLATFORM_APPLICATION_ARN="arn:aws:sns:ap-south-1:ACCOUNT:app/GCM/YOUR_APP"
.\aws\scripts\deploy.ps1 -Region ap-south-1
```

## Phase 11 — Configure Android

1. Open `android/` in Android Studio.
2. Add `android/app/google-services.json`.
3. Let Android Studio create/manage `android/local.properties`.
4. Add:

   ```properties
   QUAKEMESH_API_BASE_URL=https://YOUR_API.execute-api.ap-south-1.amazonaws.com/prod
   QUAKEMESH_API_KEY=YOUR_DEMO_WRITE_KEY
   ```

   You can read both values from `artifacts/runtime-config.json` after AWS deployment.

5. If wrapper scripts/JAR are absent, either let Android Studio sync the project or run once from an installed Gradle:

   ```powershell
   gradle wrapper --gradle-version 9.6.0
   ```

6. Build/install on an Android emulator with Google Play services.
7. Build/install the same app on your physical Android phone.
8. Grant location and notification permissions.
9. Press **Start monitoring**.

## Phase 12 — Validate Android → AWS → FCM

Confirm in this order:

1. app starts sensor foreground service;
2. heartbeat appears in DeviceState;
3. the device has an SNS endpoint ARN after FCM token registration;
4. simulator distributed scenario creates a confirmed event;
5. Android device lies in a targeted H3 cell/frontier for the test setup;
6. FCM warning arrives;
7. AlertDelivery shows the Android device/event record.

Do not lower thresholds randomly to make the demo pass. If you change experiment configuration, record the exact values.

## Phase 13 — Capture review evidence

For your cloud-computing review/final report, capture evidence of:

- IoT Things and topic flow;
- IoT Rule;
- Lambda functions/logs;
- DynamoDB records;
- H3 footprint/frontier dashboard;
- negative same-cell case;
- positive distributed case;
- AlertDelivery records;
- Android notification;
- experiment trace JSON;
- CloudWatch alarms/metrics;
- architecture diagram from the report/docs.

Never screenshot/expose private keys, AWS secret keys, Firebase service-account secrets, or full API-key values.

## Phase 14 — Teardown when finished

```powershell
.\aws\scripts\destroy.ps1 -Region ap-south-1
```

The teardown performs cloud discovery for `QM-SIM-` Things as well as local-certificate discovery, so stale simulator principals do not silently block IoT policy deletion. If you want to inspect cleanup first:

```powershell
.\.venv\Scripts\python.exe aws\scripts\delete_devices.py --region ap-south-1 --discover --dry-run
```

The S3 experiment archive is retained on purpose. Delete that bucket manually only when you are certain you no longer need the evidence and want to eliminate its remaining storage cost.

## If something fails

Read `docs/QM-OPS-001_OPERATIONS.md` before changing code. It contains failure-specific checks for H3, API keys, IoT policy/client IDs, FCM, CDK and teardown.
