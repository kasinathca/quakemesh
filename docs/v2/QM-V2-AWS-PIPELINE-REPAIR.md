# QuakeMesh V2 AWS pipeline repair and live-verification runbook

## Scope and evidence

The `qm-20261019-070119-248a` launch proved infrastructure creation, API smoke writes, provisioning of 25 IoT Things, broker acceptance of 33 QoS-1 messages, and exact-session cleanup. It did **not** prove IoT Rule delivery, evidence persistence, correlation, dispatch, or FCM delivery. The retained summary reported 25 scenario devices, zero confirmed events, and zero matching alerts. The original CloudWatch logs and DynamoDB tables were deleted with the clean ephemeral stack, so the precise live failure stage cannot be recovered retrospectively.

Offline reconstruction found two independent correctness hazards in the production Lambda path:

1. DynamoDB Streams order records by table commit order, while the correlator previously evaluated only backward from each inserted record's device observation timestamp. A record with an older observation timestamp can arrive last, after newer evidence was committed; the old evaluation excluded that newer evidence and could leave a legitimate cluster permanently unconfirmed. The correlator now reads a bounded window on both sides of the arriving timestamp and runs the unchanged backward-looking detector at the latest committed observation time. The eight-second detector meaning is preserved.
2. The dispatcher previously queried `cell-lastseen-index` immediately after an event was written. DynamoDB GSIs are eventually consistent, so a valid event could resolve zero recipients and the successful stream invocation would not retry. Dispatch now uses a paginated, strongly consistent base-table scan. This is intentionally correctness-first for the bounded academic review fleet.

These defects are proven by offline regression tests. They are plausible explanations for the failed live run, but are not represented as retrospective CloudWatch proof.

## Second controlled-session evidence — 2026-10-19

Session `qm-20261019-101849-9efb` deployed successfully with the expected SNS application ARN and a 90-minute expiry. HTTPS smoke ingestion passed. Twenty-five session-owned IoT simulators published 25 heartbeats and eight triggers; all 33 MQTT publish operations reported success. The durable pre-teardown capture counted 26 device rows, nine evidence rows, zero event rows, and zero alert rows. Structured logs prove 25 scenario heartbeats and eight scenario evidence inserts. The ninth evidence row was the separate physical-provenance HTTPS smoke trigger, so it must not be counted toward scenario quorum.

No structured correlator or dispatcher log row was captured. That fact alone does **not** prove non-invocation: the old collector did not preserve event-source mapping state, Lambda metrics, iterator age, raw empty-log-window metadata, or mapping health. A read-only CloudTrail event-history lookup after teardown returned no `CreateEventSourceMapping` events for the time window, so the deleted mapping UUID, creation transition and processing result cannot be reconstructed.

The retained CDK template does prove the following:

- `Evidence` used `NEW_IMAGE`; `Events` used `NEW_AND_OLD_IMAGES`.
- Both mappings referenced the corresponding table `StreamArn` intrinsic, not a hand-built ARN.
- The correlator role had `ListStreams`, `DescribeStream`, `GetShardIterator` and `GetRecords` permissions for the evidence stream. The dispatcher received the equivalent event-stream grant from the CDK event source.
- The Lambda functions depended on their generated role policies, and each mapping depended transitively on its function and stream.
- Correlator runtime/handler/timeout/layer were Python 3.12, `aws.lambdas.correlator.handler`, 30 seconds, and the Linux x86_64 H3 layer.
- Both mappings used `LATEST`, two retries, batch sizes 20/10, and batch bisection. Partial-batch responses were not enabled; a handler exception retries/bisects the whole batch, relying on event and alert idempotency.

What remains unprovable for the deleted session is whether a mapping reached `Enabled`, was delayed, was disabled/unhealthy, invoked a failing runtime before structured logging, or established a `LATEST` checkpoint after the nine inserts. The failure is therefore classified as an **unresolved evidence-stream-to-correlator delivery failure with two confirmed startup-control defects**, not as a proven Lambda non-invocation.

## Post-repair controlled-session evidence — 2026-10-19

Session `qm-20261019-112257-b77a` used the repaired source with a 90-minute expiry. CloudFormation completed, and the readiness gate found exactly one Enabled mapping for each exact stream ARN on its first poll. Both mappings used `TRIM_HORIZON`, had `LastProcessingResult=OK` after traffic, and invoked active Python 3.12 functions. The distributed simulator published 25 heartbeats and eight triggers with zero publish failures. AWS persisted 25 scenario devices and nine scenario evidence rows, created one authoritative confirmed scenario event, generated 17 alert records, and delivered 17 simulator alerts. Captured metrics showed two correlator invocations and one dispatcher invocation with zero errors; the sanitized diagnostic capture completed with zero capture errors.

The Firebase-enabled AWS APK was installed on `ZD222HDG42`. Monitoring registered physical device `QM-ANDROID-5f786f75-a29`, its real H3/correlation cells, and an enabled session-owned SNS endpoint. A direct SNS message explicitly labeled `CONTROLLED TEST — NOT AN EARTHQUAKE` was observed under its unique ID in the handset UI, proving physical FCM receipt without representing the message as a detected event. Normal handset movement independently persisted physical evidence `QM-ANDROID-5f786f75-a29:169`; correlation evaluated it as one physical device in one cell, with no scenario run ID and no event. The sole confirmed event therefore remained scenario-only. ACK was not applicable because the direct controlled test intentionally had no authoritative alert-table row.

Live capture also exposed and repaired two local-only reliability issues: boto3 mapping timestamps are now serialized safely by the diagnostic CLI, and the local runtime now evaluates out-of-order triggers at the latest persisted observation just like the AWS correlator. A deterministic reverse-arrival test covers the latter.

## Stream activation repair

Both streams are newly created, empty, and owned by one short-lived review session. Their mappings now use `TRIM_HORIZON`. For this lifecycle, replaying from the oldest retained record means an insert made after table creation but before poller activation remains eligible. `LATEST` can exclude that pre-activation interval. Replays are safe within the application contract: event creation uses a stable key and conditional write, event merging does not increment a version when no evidence changes, dispatcher claims use stable event/device alert IDs, and handset messages deduplicate by alert ID. Detection thresholds remain unchanged.

START now runs `verify_stream_mappings.py` immediately after runtime-config export and before the smoke trigger, IoT provisioning, or distributed simulation. The bounded 180-second gate discovers the actual CloudFormation table and Lambda physical IDs, describes both DynamoDB streams, enumerates each function's event-source mappings, requires an exact stream-ARN match, and polls until stream status, Lambda state/update status and mapping state are healthy. `Disabled`, `Failed`, incorrect-ARN, wrong-view and unhealthy processing-result states fail with durable details; transitional states are polled without arbitrary fixed sleeps. A readiness failure enters the existing diagnostics-before-exact-teardown path.

The eight positive devices occupy four distinct resolution-7 H3 cells: `8760145a6ffffff`, `87618925bffffff`, `876189258ffffff`, and `87618925effffff`. Their maximum pairwise grid distance is 3, below the configured maximum of 6. The simulator geography therefore satisfies the configured 4-device/3-cell spatial quorum.

## Pipeline contract and proof points

| Stage | Input and validation | Persisted result / proof |
|---|---|---|
| Virtual phone | V1 heartbeat then trigger; monotonic sequence; coordinates and motion | Trace records broker acknowledgement, not Lambda success |
| AWS IoT | mTLS Thing identity; Thing-scoped policy; session topic | QoS-1 proves broker acceptance only |
| IoT Rule / ingress | `topic_path`; session, topic/device, clock, schema, sequence and motion validation | `HEARTBEAT_PERSISTED`, `EVIDENCE_PERSISTED`, or `EVIDENCE_REJECTED`; device/evidence tables |
| Evidence stream / correlator | INSERT; paginated strong evidence reads; scenario/run isolation | `CORRELATION_EVALUATED` includes reason, device/cell counts and cells; event row |
| Event stream / dispatcher | Confirmed INSERT/MODIFY; strong recipient read; provenance/run match | `ALERT_TARGETS_RESOLVED`, `ALERT_DELIVERY_COMPLETED`; alert row |
| Delivery | Scenario MQTT; physical devices may also receive SNS/FCM | MQTT trace or handset observation; `SENT` row |
| API/dashboard | Paginated scans and V2 envelopes | Session-filtered device/event/alert views |

Physical HTTPS ingress rejects `X-QuakeMesh-Run-Id`; MQTT ingress labels evidence `scenario` and binds it to the deployment session. The two provenances cannot combine to reach quorum.

## Durable failure diagnostics

Warm-up writes sanitized files beneath `artifacts/review/diagnostics/<session-id>/`, outside ephemeral `artifacts/aws-v2/<session-id>/`. The stream gate writes `stream-readiness.json`; the warm-up verifier writes `summary.json`, `warmup-observations.json`, `simulator-summary.json`, and `diagnostics.txt`. On START failure, `capture_diagnostics.py` runs before STOP and best-effort captures table counts, exact table stream metadata, Correlator/Dispatcher names and ARNs, mapping UUID/state/reason/processing result/last-modified/configuration, Lambda handler/runtime/state, function invocation/error/throttle/iterator-age metrics, the exact log function list and time window, session-scoped structured logs, and raw Lambda error signatures. Files include `capture-summary.json`, `stream-integrations.json`, `lambda-metrics.json`, `pipeline-timeline.json`, `correlation-diagnostics.json`, and `aws-errors.json`.

Unavailable or delayed metrics, missing log groups, empty windows, permission errors and partial capture are explicit. Capture failure never prevents cleanup. API keys, authorization values, credentials, private material, secrets, and tokens are redacted or excluded.

Failure labels are evidence-based: no scenario device/evidence is `INGRESS_FAILURE`; evidence without a confirmed event is `CORRELATION_FAILURE`; a valid event without a matching alert is `ALERT_DISPATCH_FAILURE`; otherwise the verifier retains `WARMUP_VERIFICATION_FAILURE`.

## Offline validation

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD"
.\.venv\Scripts\python.exe -m pytest -q --basetemp artifacts\pytest-validation
.\.venv\Scripts\python.exe -m ruff check src local_runtime simulator aws scripts tests
.\scripts\validate.ps1
Push-Location .\android
.\gradlew.bat testDebugUnitTest assembleDebug --no-daemon
Pop-Location
```

Offline success proves deterministic application behavior and build readiness. It does not prove AWS IoT Rule invocation, deployed Lambda behavior, SNS endpoint registration, or FCM handset delivery.

## Approved live-test procedure

Run only after explicit cost approval. `start.ps1` now defaults the reusable SNS application to the exact ARN below, validates its account and region against STS, exports it as `QM_SNS_PLATFORM_APPLICATION_ARN`, and passes it explicitly to `deploy.ps1`. The environment assignment shown here is therefore an optional visible preflight assertion rather than a hidden prerequisite.

```powershell
Set-Location "C:\Users\kasin\Projects\CLOUD PROJECT\QuakeMesh-v1.0.1\QuakeMesh"

git branch --show-current
git status --short
.\scripts\review\prepare.ps1
.\scripts\review\status.ps1 -Profile quakemesh-demo -Region ap-south-1

aws sts get-caller-identity --profile quakemesh-demo --region ap-south-1 --no-cli-pager
aws configure get region --profile quakemesh-demo
$env:QM_SNS_PLATFORM_APPLICATION_ARN = "arn:aws:sns:ap-south-1:101541767123:app/GCM/QuakeMesh-FCM-Demo"

adb devices -l
adb -s ZD222HDG42 shell getprop ro.product.model

.\scripts\review\start.ps1 -Profile quakemesh-demo -Region ap-south-1 -DurationMinutes 90 -Devices 25 -AwsCliPath "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
.\scripts\review\status.ps1 -Profile quakemesh-demo -Region ap-south-1
Get-ChildItem .\artifacts\review\diagnostics -Recurse

adb -s ZD222HDG42 install -r .\android\app\build\outputs\apk\debug\app-debug.apk
adb -s ZD222HDG42 logcat -c
adb -s ZD222HDG42 logcat | Select-String "QuakeMesh|FirebaseMessaging|Fcm"

$state = Get-Content .\artifacts\review\current-session.json -Raw | ConvertFrom-Json
$runtime = Get-Content $state.runtime_config -Raw | ConvertFrom-Json
Invoke-RestMethod ($runtime.api_base_url.TrimEnd('/') + '/v1/devices?limit=1000') |
    Select-Object -ExpandProperty data | Select-Object -ExpandProperty items |
    Where-Object provenance_type -eq 'physical'
Invoke-RestMethod ($runtime.api_base_url.TrimEnd('/') + '/v1/events?limit=500')
Invoke-RestMethod ($runtime.api_base_url.TrimEnd('/') + '/v1/alerts?limit=2000')

aws sns list-endpoints-by-platform-application `
  --platform-application-arn $env:QM_SNS_PLATFORM_APPLICATION_ARN `
  --profile quakemesh-demo --region ap-south-1 --no-cli-pager

.\scripts\review\stop.ps1 -Profile quakemesh-demo -Region ap-south-1
.\scripts\review\status.ps1 -Profile quakemesh-demo -Region ap-south-1
Get-Content .\artifacts\review\last-teardown.json -Raw
```

Interpret each milestone independently:

- **APK BUILD SUCCESS**: Gradle produced an APK.
- **APK INSTALLED**: ADB installed that APK on the named handset.
- **PHONE MONITORING**: permissions are granted and the foreground service is running.
- **HEARTBEAT ACCEPTED**: the API returned an accepted physical heartbeat receipt.
- **SNS ENDPOINT REGISTERED**: the heartbeat FCM token maps to an enabled endpoint.
- **CLOUD EVIDENCE PERSISTED**: a physical trigger passed validation, sequence, clock, and motion gates.
- **CLOUD EVENT CONFIRMED**: independent quorum and spatial rules created an event. One phone cannot do this alone.
- **FCM NOTIFICATION DELIVERED**: the data message was observed on the handset.
- **ALERT ACKNOWLEDGED**: the phone's idempotent ACK is present in the alert record.

AWS post-fix stream processing and physical FCM receipt were live-verified in the controlled session above. Alert acknowledgement remains unverified because the controlled direct message was intentionally not inserted as an authoritative alert record.

## Final cleanup audit for the verified live session

The exact session `qm-20261019-112257-b77a` was audited and cleaned on 2026-10-19. At `13:20:19Z`, the stack was still `CREATE_COMPLETE` even though its `at(2026-10-19T12:53:03)` Scheduler schedule was enabled, so the expiry fail-safe had not completed on time. The guarded review teardown then verified the account, region, stored session metadata, and complete stack ownership tags before deleting anything.

CloudFormation removed the stack and its captured 96-resource inventory, and the cleanup removed 25 dynamic simulated IoT Things. The first post-delete verification correctly returned `INCOMPLETE` because one SNS endpoint remained. Its non-secret `CustomUserData` was verified as the exact marker `QuakeMesh:qm-20261019-112257-b77a`; that endpoint ARN was deleted without modifying the reusable `QuakeMesh-FCM-Demo` platform application. A repeated independent teardown verification at `13:25:51Z` returned `CLEAN` with no findings or errors.

The Resource Groups Tagging API continued to return two DynamoDB stream ARNs after cleanup. Both were stale deleted-stream index entries: the underlying tables and all resources in the captured inventory were independently absent. The shared `CDKToolkit`, its content-addressed assets, and the enabled reusable SNS platform application were intentionally retained.

Local ports 8000, 8080, and 8081 were stopped; managed review processes and active review state were removed; and Android configuration was restored to `LOCAL/DEFAULT`. Evaluation outputs and the successful session diagnostics were preserved. The sanitized audit is `artifacts/review/final-cleanup-report.json`; the authoritative teardown evidence and captured inventory are under `artifacts/review/diagnostics/qm-20261019-112257-b77a/`.

The same-day Cost Explorer query filtered by the exact `SessionId` tag returned an estimated USD 0. This value is subject to AWS reporting delay and must not be interpreted as proof that the completed session incurred no historical cost. The cleanup conclusion is limited to the absence of active exact-session resources capable of continuing session-owned usage.
