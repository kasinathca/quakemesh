# QuakeMesh

**Cloud-native geographically diverse smartphone motion-corroboration prototype**  
Academic cloud-computing project · AWS serverless backend · H3 spatial indexing · Python virtual-phone fleet · Android client · live dashboard

> **Important scope statement:** QuakeMesh is an experimental software prototype. A “confirmed event” means the configured cloud corroboration rules were satisfied. It is **not** an official earthquake declaration, does not estimate magnitude or epicentre, and is not validated for life-safety use.

> **V2 engineering status:** the local control plane, authoritative scenario engine, provenance isolation, structured telemetry stream, evidence export/reset/ACK contracts, and React operations dashboard are implemented and locally verified. The Android V2 networking, monitoring UI, local API configuration, alert identity, and ACK client now build and lint successfully; emulator/physical-device behavior and live FCM remain unverified. Strict ephemeral AWS sessions and AWS V2 deployment are not yet implemented or verified. See [`docs/v2/QM-V2-COMPLETION-REPORT.md`](docs/v2/QM-V2-COMPLETION-REPORT.md).

## What is implemented

This repository contains a complete V1 engineering baseline that can be demonstrated locally on one Windows PC and then deployed to AWS:

- shared Python domain engine for schema validation, H3 canonicalization, spatial/temporal correlation and event lifecycle;
- local FastAPI + SQLite V2 control plane with versioned envelopes, stable errors, request IDs, REST snapshots, and SSE stage telemetry;
- one authoritative scenario service used by dashboard and PowerShell CLI, with atomic single-run policy and physical/scenario/run provenance isolation;
- deterministic Python virtual-phone fleet with validated effective parameters, repeatable loss, jitter, and propagation;
- AWS IoT Core MQTT/mTLS ingestion with Thing-scoped policy;
- IoT Rules → Lambda ingress;
- DynamoDB device state, TTL evidence, authoritative event state and alert-delivery records;
- strongly consistent correctness-first correlator with versioned conditional event writes;
- H3 Detection Footprint and Warning Frontier;
- MQTT alert dispatch for simulator Things;
- optional Amazon SNS → Firebase Cloud Messaging path for Android;
- API Gateway REST API, with API-key-gated write fallback and public read-only dashboard endpoints;
- EventBridge scheduled event resolution;
- CloudWatch Lambda error alarms and X-Ray tracing;
- encrypted/versioned S3 experiment archive;
- static React/strict-TypeScript/Vite operations dashboard with bundled Leaflet, H3 polygon overlays, nine feature views, logs, ACK, reset, and export;
- Android foreground accelerometer/location client + FCM warning receiver;
- AWS provisioning/deploy/destroy scripts;
- JSON schemas, controlled documentation, experiment plan and requirement traceability;
- automated tests, secret scanning and release auditing.

## Architecture

```text
                           SINGLE DEVELOPMENT PC

 Python virtual phones ─────────────┬──────────────────────────────┐
                                    │                              │
 Android emulator(s) ───────────────┤                              │
                                    │                              │
 Dashboard ◄──── read API ──────────┤                              │
                                    │                              │
                         local mode │                  AWS mode    │
                                    ▼                              ▼
                         FastAPI + SQLite          AWS IoT Core MQTT/mTLS
                                    │                       │
                         Shared QuakeMesh Core             IoT Rules
                                    │                       │
                                    │                       ▼
                                    │                 Ingress Lambda
                                    │                       │
                                    │              ┌────────┴────────┐
                                    │              ▼                 ▼
                                    │       DeviceState DDB      Evidence DDB
                                    │                                │ stream
                                    │                                ▼
                                    │                         Correlator Lambda
                                    │                                │
                                    │                                ▼
                                    │                            Events DDB
                                    │                                │ stream
                                    │                                ▼
                                    │                         Dispatcher Lambda
                                    │                          │             │
                                    │                          ▼             ▼
                                    │                       MQTT         SNS → FCM
                                    │                          │             │
                                    │                    virtual phones   Android
                                    │
                                    └────────────────────────────────────────────

 Physical Android phone ── HTTPS/API-key demo ingress ──► API Gateway ─► same cloud persistence
```

The primary cloud simulator path is AWS IoT Core with per-device X.509/mTLS. The HTTPS path is a controlled academic fallback for Android; its API key is **not** presented as production-grade mobile authentication.

## Core event logic

A single phone never confirms an event. The shared detector requires all configured conditions:

1. evidence is recent enough to fall inside the active time window;
2. enough **distinct devices** contributed;
3. enough **distinct coarse H3 cells** contributed;
4. the evidence belongs to a spatially coherent H3 component;
5. duplicate/replayed per-device sequences cannot inflate evidence.

Default prototype parameters are in `src/quakemesh_core/config.py`:

| Parameter | Default | Meaning |
|---|---:|---|
| device H3 resolution | 9 | transient coordinate → device cell |
| correlation H3 resolution | 7 | diversity/footprint/targeting cell |
| evidence window | 8 s | active evidence age |
| minimum devices | 4 | distinct device threshold |
| minimum coarse cells | 3 | spatial-diversity threshold |
| max cluster grid distance | 6 | coarse-cell coherence rule |
| warning ring | k=1 | cells surrounding Detection Footprint |
| event merge window | 20 s | active-event compatibility window |
| resolve inactivity | 30 s | confirmed → resolved timeout |
| max device/cloud clock skew | 120 s | rejects implausibly stale/future observations |
| motion RMS gate | 0.75 | defensive cloud/local trigger acceptance gate |
| motion peak gate | 1.80 | defensive cloud/local trigger acceptance gate |

These are **experimental engineering parameters**, not seismological constants.

## Detection Footprint and Warning Frontier

- **Detection Footprint:** coarse H3 cells that contributed to the corroborated evidence component.
- **Warning Frontier:** configured H3 neighborhood ring around the footprint, excluding the footprint itself.

They are software/geospatial constructs. The Warning Frontier is **not** a seismic wavefront or predicted arrival-time boundary.

## Repository layout

```text
QuakeMesh/
├── src/quakemesh_core/         # transport-independent domain logic
├── local_runtime/              # FastAPI + SQLite local vertical slice
├── simulator/                  # deterministic virtual-phone fleet
├── aws/
│   ├── infrastructure/         # AWS CDK V2 stack
│   ├── lambdas/                # ingress/correlation/API/dispatch/resolution
│   └── scripts/                # layer build, deploy helpers, provisioning
├── android/                    # Android physical/emulator app source
├── dashboard/                  # browser operations dashboard
├── schemas/                    # JSON message contracts
├── experiments/                # scenario registry
├── tests/                      # executable tests
├── scripts/                    # setup/validation/local-demo helpers
├── docs/                       # controlled software documentation
├── artifacts/                  # generated runtime evidence; gitignored
├── NEXT_STEPS.md               # exact order to continue on your PC
└── NEW_REPO_SETUP_AND_PUSH.md  # create/push a clean new GitHub repository
```

## Prerequisites for your Windows PC

For the local path:

- Python 3.10+; **Python 3.12 recommended** because Lambda also uses Python 3.12;
- PowerShell;
- Git.
- Node.js 20+ and npm for a missing/stale dashboard production build and frontend validation.

For AWS deployment additionally:

- AWS CLI v2, configured credentials;
- Node.js 22 LTS recommended;
- npm/npx.

For Android additionally:

- current Android Studio;
- JDK 17 (Android Studio bundled JDK is normally suitable);
- Android SDK/API 37;
- an Android emulator with Google Play services for FCM, and/or your physical Android phone.

## Fastest local demonstration

Open PowerShell in the extracted repository:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\validate.ps1
```

Then either use the convenience script:

```powershell
.\scripts\demo_local.ps1 -Scenario distributed -Devices 25
```

or run the components separately.

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

Dashboard:

```text
http://127.0.0.1:8080
```

Expected high-level behavior:

| Scenario | Expected result |
|---|---|
| `isolated` | no confirmed event |
| `same-cell` | no confirmed event because spatial diversity is insufficient |
| `distributed` | confirmation expected under default configuration |
| `degraded` | conditional confirmation if enough evidence survives loss/jitter |

Simulator truth remains only in simulator trace metadata and is never sent to the detector. Controlled evidence carries its authoritative run ID. Physical propagation changes `observed_at_ms`; simulated network jitter delays delivery instead of falsifying observation time.

## AWS deployment

> **V2 status warning:** The AWS implementation and deployment commands in this section belong to the retained V1 cloud baseline. They are preserved as implementation reference and must not be treated as the V2 cloud architecture. Do not deploy this stack as V2 until session-scoped ownership, expiry/cleanup, zero-resource verification, and V2 API/provenance/telemetry parity have been implemented and verified.

First complete local setup and validation, then verify AWS credentials:

```powershell
aws sts get-caller-identity
```

Deploy into Mumbai by default:

```powershell
.\aws\scripts\deploy.ps1 -Region ap-south-1
```

The deploy script performs the important platform-sensitive work automatically:

- builds the H3 Lambda layer as a **manylinux x86-64 CPython 3.12** artifact even when run from Windows;
- creates an isolated CDK Python environment;
- forces the CDK CLI to execute `app.py` using that exact environment’s Python path;
- runs CDK synth/bootstrap/deploy with pinned Toolkit CLI 2.1140.0;
- exports the account-specific API key/endpoint configuration into `artifacts/runtime-config.json`.

The exported runtime file is gitignored because it contains the controlled-demo API key.

Provision 25 simulator Things/certificates:

```powershell
.\aws\scripts\provision_simulators.ps1 -Count 25
```

Run a real AWS IoT scenario:

```powershell
.\aws\scripts\run_aws_scenario.ps1 -Transport mqtt -Scenario distributed -Devices 25
```

You can also exercise the gated HTTPS fallback:

```powershell
.\aws\scripts\run_aws_scenario.ps1 -Transport http -Scenario distributed -Devices 25
```

Upload an important simulator trace to the retained S3 experiment archive:

```powershell
.\aws\scripts\upload_trace.ps1 -Trace artifacts\traces\YOUR_TRACE.json -Region ap-south-1
```

The uploader validates QuakeMesh trace schema `1.0`, computes SHA-256, stores it as S3 object metadata, and never uploads IoT private-key directories.

## Firebase / Android

AWS deployment works without Firebase. MQTT simulator alerts remain available.

To add Android FCM:

1. follow `docs/FIREBASE_SNS_SETUP.md`;
2. place Firebase `google-services.json` at `android/app/google-services.json`;
3. create the SNS FCM platform application and set its ARN before CDK deploy/update;
4. add the generated API URL/API key to Android `local.properties` as shown in `android/local.properties.example`;
5. open `android/` in Android Studio, sync/build/install;
6. grant location/notification permissions and press **Start monitoring**.

The Android app has no manual “earthquake confirmed” button. It performs a local motion prefilter and sends a trigger; cloud corroboration remains authoritative.

For local emulator development, a debug build defaults to `http://10.0.2.2:8000`. Only the debug manifest permits cleartext traffic, and only for emulator/host loopback aliases. A local FastAPI connection does not require an API key. Release builds have no fallback URL and retain the HTTPS-only main-manifest policy. Override either mode with `QUAKEMESH_API_BASE_URL` in ignored `android/local.properties`.

## Android build baseline

The Android project is intentionally modern rather than based on stale templates:

- AGP 9.4.0;
- Gradle 9.6.0;
- AGP built-in Kotlin;
- compile/target SDK 37;
- min SDK 26;
- Firebase BoM 34.18.0;
- google-services Gradle plugin 4.5.0.

The Gradle wrapper is restored. On 2026-10-07 the current Windows host successfully ran `testDebugUnitTest` (no test sources), `assembleDebug`, and `lintDebug`; this verifies compilation, packaging, and static Android checks, not emulator, physical sensor/location, network, or FCM behavior.

## AWS resources

> The resources below describe the retained V1 AWS baseline, not the final V2 session-scoped cloud architecture.

The CDK stack creates only managed/serverless services:

- AWS IoT Core rules/policy;
- Lambda;
- DynamoDB;
- API Gateway;
- EventBridge;
- SNS integration hooks;
- S3 experiment archive;
- CloudWatch alarms/X-Ray.

It deliberately creates **no VPC, NAT Gateway, EC2, ECS, EKS or RDS**.

## Privacy design

Raw latitude/longitude appears in an inbound device message because H3 must be calculated somewhere. QuakeMesh then persists:

- H3 device cell;
- H3 correlation cell;
- device/sequence/timestamps/motion features.

The application device/evidence schemas do not retain raw latitude/longitude. H3 still represents approximate location and must be treated accordingly.

## Security design

- IoT clients: per-Thing X.509/mTLS;
- Thing policy: client/topic identity scoped to Thing name;
- ingress: verifies topic device ID equals payload device ID;
- HTTPS writes: API Gateway API key required;
- API key/runtime config/certs/Firebase files: gitignored;
- event updates: conditional version writes;
- evidence/device replay protection: monotonic sequence + conditional persistence;
- alert dispatch: retry-safe `DISPATCHING`/`FAILED`/`SENT` state per event/device, with client event-ID deduplication for the crash-after-send window.
- observation timestamps: bounded clock-skew validation before persistence/correlation.
- trigger metrics: defensive motion gate is enforced again at ingest even though Android prefilters locally.

The Android API key can be extracted from an APK and is therefore only a controlled-demo safeguard, not production authentication.

## Validation

Use:

```powershell
.\scripts\validate.ps1
```

Release validation includes:

- Python byte-compilation;
- the complete pytest suite (including control-plane concurrency, provenance, export/reset/ACK, and V2 API integration);
- repository-critical Ruff plus broader professional rules on V2-modified modules;
- JSON Schema contract/privacy checks;
- secret scan;
- PowerShell launch tests;
- locked npm install, strict TypeScript, ESLint, Vitest, and production Vite build;
- Playwright local scenario/ACK/export/disconnect and responsive browser E2E when Chromium is installed;
- repository contract audit.

A real-H3 integration test is included. If `h3` is unavailable, that one test explicitly skips; after `scripts/setup.ps1` on your PC it should execute rather than skip.

AWS deployment, Firebase delivery and a real Android build/device run are environment/account-dependent validations and are intentionally reported separately instead of being falsely claimed by this repository. See `VALIDATION_REPORT.md` for the release-time evidence and exact boundaries.

## Documentation

Start with:

- `docs/00_DOCUMENT_INDEX.md`
- `docs/AI_READER.md`
- `docs/QM-SRS-001_REQUIREMENTS.md`
- `docs/QM-ARCH-001_ARCHITECTURE.md`
- `docs/QM-TRC-001_TRACEABILITY.md`
- `docs/QM-OPS-001_OPERATIONS.md`

The controlled documentation endpoint is `QM-OPS-001`; implementation should now take priority over endlessly creating new documents.

Release evidence and per-file integrity are in `VALIDATION_REPORT.md` and `SOURCE_MANIFEST.txt`.

## Creating the GitHub repository

Do **not** upload the ZIP contents blindly before running the checks. Follow:

```text
NEW_REPO_SETUP_AND_PUSH.md
```

It includes clean Git initialization, the pre-push secret scan, both GitHub web and `gh` CLI paths, branch setup and first push.

## Teardown

After AWS experiments:

```powershell
.\aws\scripts\destroy.ps1 -Region ap-south-1
```

Simulator certificates/Things are removed before the stack. The S3 experiment archive uses `RETAIN` deliberately; delete the retained bucket manually only after you no longer need the evidence.

## License

MIT for the project source. Third-party dependencies retain their own licenses.
