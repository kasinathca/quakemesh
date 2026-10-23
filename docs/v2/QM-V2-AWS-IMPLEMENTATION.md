# QuakeMesh V2 AWS implementation

Status date: 2026-10-08 (Asia/Calcutta)

## Status

This 2026-10-08 foundation statement was superseded by later live validation. The AWS V2 serverless system is implemented and has been repeatedly deployed in account `101541767123`, region `ap-south-1`. Final session `qm-20261023-190030-20bc` verified interactive AWS Scenario Lab execution, production H3 corroboration, USB-disconnected authoritative SNS/FCM delivery, Android receipts/acknowledgement, and exact-session CLEAN teardown. The detailed evidence is in `QM-V2-FINAL-DEMO-VALIDATION.md`.

## Architecture

Each demo is an isolated CloudFormation stack named `QuakeMesh-V2-Demo-<session-id>`. The current stack owns API Gateway, seven Lambdas (API, ingress, correlator, dispatcher, resolver, scenario runner, and expiry cleanup), five on-demand DynamoDB tables (device, evidence, event, alert, and scenario/run state), two IoT rules, a session-specific IoT policy, an EventBridge resolution schedule, a one-time EventBridge Scheduler cleanup target, explicit one-week Lambda log groups, X-Ray tracing, and error alarms. No EC2, VPC, NAT Gateway, RDS, ECS, EKS, or retained S3 bucket is created.

HTTPS from Android is physical provenance. AWS IoT simulator topics are session-specific and are stored as scenario provenance with the session ID as the run partition. Correlation queries only the inserted evidence partition, and active event merging and alert targeting retain the same provenance/run boundary. Observation payloads remain schema `1.0`; API responses use V2 envelopes.

## API

Implemented routes:

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | mode, session, region, version, expiry |
| POST | `/v1/devices/heartbeat` | physical HTTPS heartbeat; API key required |
| POST | `/v1/evidence/trigger` | physical HTTPS trigger; API key required |
| GET | `/v1/devices` | safe device state without FCM endpoint ARNs |
| GET | `/v1/events` | authoritative events with footprint/frontier polygons |
| GET | `/v1/alerts` | target/delivery/ACK records |
| POST | `/v1/alerts/{alert_id}/ack` | idempotent Android/dashboard ACK; API key required |

Success and error bodies match the local V2 envelope and carry `X-Request-ID`. The first AWS slice intentionally rejects an HTTPS `X-QuakeMesh-Run-Id`; controlled simulation uses the isolated IoT topic path instead of falsely storing simulator traffic as physical evidence.

## DynamoDB ownership and data

The stack owns device-state, evidence, event, alert-delivery, and scenario/run-state tables. Device keys include provenance/run/device identity. Evidence time buckets also include provenance and run, preventing physical/scenario cross-corroboration. Evidence uses a short TTL; all tables use `RemovalPolicy.DESTROY` and are deleted with the exact session stack. Event, alert, and run records include session and provenance metadata.

## Observability

Structured JSON log stages include API receipt, ingress receipt, heartbeat/evidence persistence, correlation evaluation, event transition, alert delivery, and acknowledgement. Useful identifiers include request, session, device, evidence, event, alert, provenance, and run IDs. Raw coordinates, API keys, Firebase tokens, and credentials are not logged.

When the optional SNS platform application is configured, the dispatcher emits a high-priority, data-only FCM HTTP v1 message. This ensures `FirebaseMessagingService` receives the same `alert_id`, event identity/version/status, target device, and creation timestamp in foreground and background paths so Android can deduplicate, persist details, notify, and explicitly ACK. Live delivery still requires account-owned Firebase/SNS configuration and a device.

## Deploy and inspect

Prerequisites are a configured AWS CLI, authenticated account, Python environment from `scripts/setup.ps1`, Node/npx, and permission to create the listed serverless resources.

```powershell
.\aws\scripts\deploy.ps1 -Region ap-south-1 -DurationMinutes 120
```

The command creates a unique session, verifies account identity, refuses an existing same-name stack, builds the pinned H3 Lambda layer, synthesizes, deploys, and writes ignored ownership/runtime metadata to `artifacts/aws-v2/<session-id>/runtime-config.json`. That file contains the controlled-demo API key and must not be committed.

Run the real API smoke path:

```powershell
.\.venv\Scripts\python.exe aws\scripts\smoke_test.py `
  --config artifacts\aws-v2\<session-id>\runtime-config.json
```

Provision and run session-owned IoT simulators:

```powershell
.\aws\scripts\provision_simulators.ps1 -SessionId <session-id> -Count 25
.\aws\scripts\run_aws_scenario.ps1 -SessionId <session-id> -Scenario distributed -Devices 25
```

## Deterministic teardown

```powershell
.\aws\scripts\destroy.ps1 -SessionId <session-id> -Region ap-south-1
```

Teardown refuses to act without matching local account/region/session/stack metadata. It deletes only simulator Things with the exact session prefix, destroys only the exact session stack, then checks CloudFormation absence, session tags, and exact-prefix IoT Things. The report is `CLEAN` only when no owned resources or verification errors remain; access denial is `INCOMPLETE`.

CDK bootstrap resources are shared account prerequisites and are not claimed as session-owned or removed. At `ExpiresAt`, a one-time Scheduler invocation runs the session cleanup Lambda. It selects IoT Things by both exact `SessionId` attribute and exact simulator name prefix, verifies QuakeMesh ownership, refuses shared certificates or unexpected policies, removes only verified session simulator credentials, and requests deletion of its own exact CloudFormation stack. Failures leave the stack available for bounded Scheduler retries. This is a safety backstop; operators must still use deterministic teardown and require a `CLEAN` verification report.

## Dashboard cloud mode

After deployment, serve the same dashboard against the real session endpoint:

```powershell
.\scripts\run_dashboard.ps1 -Port 8080 `
  -ConfigPath artifacts\aws-v2\<session-id>\runtime-config.json
```

The ignored production `config.js` receives the demo API URL/key, region, session, and expiry. The UI labels the environment `AWS V2 Demo`, reads real device/event/alert/run data, controls the real AWS Scenario Lab, displays experiment history/stages, supports safe selection reset and the real ACK route, and shows API connection/session state. Local evidence-file export and detector-configuration reads remain unavailable in AWS mode. Starting without `-ConfigPath` resets the dashboard to Local V2 configuration.

## Cost and current limitations

All application resources are on-demand/serverless. Normal demo traffic should remain low-cost, but deployment creates billable AWS resources and must be torn down. The exact account and price are not inferred locally.

Verified in account `101541767123`, region `ap-south-1`: authenticated deployment, API health/writes, 25 session IoT simulators, IoT Rule ingestion, DynamoDB persistence, enabled `TRIM_HORIZON` stream mappings, correlator/dispatcher invocation without errors, one authoritative scenario event, 17 alerts, physical heartbeat/H3 registration, an enabled session SNS endpoint, controlled handset FCM receipt, and exact-session teardown. The final audit found all 96 captured stack resources absent and zero active QuakeMesh stacks. Automatic expiry is **not** verified: the successful session remained `CREATE_COMPLETE` after its scheduled time and required guarded manual STOP.
