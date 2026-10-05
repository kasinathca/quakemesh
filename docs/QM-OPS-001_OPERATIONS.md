# QM-OPS-001 — Operations Runbook

This is the final controlled document in the planned documentation phase.

## 1. Local setup

From Windows PowerShell at repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\validate.ps1
```

Python 3.12 is recommended. `setup.ps1` creates `.venv` and installs the pinned runtime/dev dependencies.

## 2. Local demonstration

Terminal A:

```powershell
.\scripts\run_local.ps1
```

Terminal B:

```powershell
.\scripts\run_dashboard.ps1
```

Terminal C:

```powershell
.\scripts\run_scenario.ps1 -Scenario isolated
.\scripts\run_scenario.ps1 -Scenario same-cell
.\scripts\run_scenario.ps1 -Scenario distributed
.\scripts\run_scenario.ps1 -Scenario degraded
```

Dashboard: `http://127.0.0.1:8080`.

## 3. AWS prerequisites

Install/configure:

- AWS CLI v2;
- Node.js 22.x or another CDK-supported LTS;
- npm/npx;
- AWS credentials with permission to create the stack resources;
- project Python environment from setup.

Confirm:

```powershell
aws sts get-caller-identity
```

## 4. AWS deployment

```powershell
.\aws\scripts\deploy.ps1 -Region ap-south-1
```

The script:

1. validates AWS identity;
2. cross-builds the Linux H3 Lambda layer;
3. creates a dedicated CDK Python venv;
4. installs `aws-cdk-lib`/constructs;
5. runs CDK synth with that venv’s absolute Python path;
6. bootstraps/deploys using the current compatible CDK CLI from npm;
7. exports API key/endpoint configuration to a gitignored local artifact.

## 5. Simulator provisioning and AWS run

```powershell
.\aws\scripts\provision_simulators.ps1 -Count 25
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario distributed -Devices 25
```

The simulator certificate directory is secret material and must never be committed.

## 6. Firebase/SNS

Create the Firebase Android app and obtain `google-services.json`. Configure an Amazon SNS FCM platform application using current FCM HTTP v1 credentials, then expose its ARN to the CDK process as `QM_SNS_PLATFORM_APPLICATION_ARN` before deployment/update. See `FIREBASE_SNS_SETUP.md`.

## 7. Android

Open `android/` in current Android Studio. Add `google-services.json` and the QuakeMesh API values to `local.properties`. Sync/build/install. Grant location/notification permissions and press **Start monitoring**.

## 8. Observation

Useful AWS areas:

- CloudFormation stack `QuakeMeshStack`;
- IoT Core MQTT test client;
- DynamoDB tables;
- Lambda CloudWatch log groups;
- CloudWatch alarms;
- API Gateway stage;
- SNS endpoint/application status.

Do not log/export private certificates or Firebase credential JSON in report evidence.

## 9. Archive an experiment trace

After a useful AWS run, upload the generated simulator trace to the retained S3 archive:

```powershell
.\aws\scripts\upload_trace.ps1 -Trace artifacts\traces\YOUR_TRACE.json -Region ap-south-1
```

The uploader accepts only QuakeMesh `trace_schema` 1.0 JSON, calculates SHA-256, and stores checksum/schema/Git-commit metadata on the S3 object. Certificate/key directories are not accepted as trace inputs.

## 10. Teardown

```powershell
.\aws\scripts\destroy.ps1 -Region ap-south-1
```

The script discovers matching `QM-SIM-` Things in AWS as well as local certificate folders, then removes simulator principals/certificates before CDK destroy so the IoT policy is not left attached. The S3 experiment archive is retained deliberately; remove it manually only after saving/deleting required evidence.

## 11. Incident handling

If a demo fails:

- local H3 import failure → rerun `scripts/setup.ps1`;
- AWS 403 on POST → API key missing/wrong; rerun `export_stack_config.py`;
- IoT authorization error → confirm client ID equals Thing name and certificate has `QuakeMeshDevicePolicy`;
- no confirmation → inspect number of surviving devices/correlation cells and timestamps; do not lower thresholds mid-run without recording config change;
- no Android FCM → verify Firebase `google-services.json`, FCM token heartbeat, SNS platform application ARN and endpoint status;
- CDK schema mismatch → use a newer CDK CLI; current AWS guidance allows a newer Toolkit with the supported construct library;
- stack destroy fails on IoT policy → run simulator deletion first;
- unexpected charges → inspect CloudWatch, API Gateway, IoT, DynamoDB, SNS and retained S3 resources and tear down unused resources.
