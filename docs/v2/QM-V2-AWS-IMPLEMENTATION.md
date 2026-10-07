# QuakeMesh V2 AWS implementation

Status date: 2026-10-08 (Asia/Calcutta)

## Status

The AWS V2 serverless foundation is implemented and locally synthesized. It is not live-deployed: this host currently has no AWS CLI, authenticated account identity, deployed endpoint, or live CloudWatch/DynamoDB evidence. The retained V1 stack must not be used as a V2 substitute.

## Architecture

Each demo is an isolated CloudFormation stack named `QuakeMesh-V2-Demo-<session-id>`. The stack owns API Gateway, six Lambdas (API, ingress, correlator, dispatcher, resolver, expiry cleanup), four on-demand DynamoDB tables, two IoT rules, a session-specific IoT policy, an EventBridge resolution schedule, a one-time EventBridge Scheduler cleanup target, explicit one-week Lambda log groups, X-Ray tracing, and error alarms. No EC2, VPC, NAT Gateway, RDS, ECS, EKS, or retained S3 bucket is created.

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

The stack owns `DeviceState`, `Evidence`, `Events`, and `AlertDelivery` tables. Device keys include provenance/run/device identity. Evidence time buckets also include provenance and run, preventing physical/scenario cross-corroboration. Evidence uses a short TTL; all tables use `RemovalPolicy.DESTROY` and are deleted with the exact session stack. Event and alert records include session and provenance metadata.

## Observability

Structured JSON log stages include API receipt, ingress receipt, heartbeat/evidence persistence, correlation evaluation, event transition, alert delivery, and acknowledgement. Useful identifiers include request, session, device, evidence, event, alert, provenance, and run IDs. Raw coordinates, API keys, Firebase tokens, and credentials are not logged.

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

The ignored production `config.js` receives the demo API URL/key, region, session, and expiry. The UI labels the environment `AWS V2 Demo`, reads real device/event/alert data, supports the real ACK route, and shows API connection/session state. Local-only Scenario Lab, experiment history, detector configuration, reset, export, and SSE telemetry are explicitly unavailable in AWS mode rather than fabricated. Starting without `-ConfigPath` resets the dashboard to Local V2 configuration.

## Cost and current limitations

All application resources are on-demand/serverless. Normal demo traffic should remain low-cost, but deployment creates billable AWS resources and must be torn down. The exact account and price are not inferred locally.

Locally verified: Python compilation, Ruff, focused AWS/cleanup contract tests, direct CDK synthesis including the one-time expiry schedule and scoped cleanup IAM, and dashboard type/lint/unit/build checks for cloud mode. Not verified: AWS authentication, deployment, API endpoint, IoT certificates/traffic, Lambda invocation, DynamoDB writes, CloudWatch logs, alarms, FCM, automatic expiry execution, or zero-resource teardown against a real account.
