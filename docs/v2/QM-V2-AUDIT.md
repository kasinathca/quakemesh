# QuakeMesh V2 forensic audit

Audit date: 2026-10-05. Scope: all source, test, schema, PowerShell, dashboard, Android, AWS infrastructure, and current operations files in this checkout.

## Baseline evidence

- Initial Python domain baseline: **41 passed, 1 skipped**. After rebuilding with native Python 3.12 and real H3, the current validation result is **50 passed**.
- The delivered `.venv` pointed to a removed Python 3.10 installation. Setup now detects and rebuilds stale native-Windows environments; MSYS2 Python is rejected because it creates an incompatible layout.
- Git verification is unavailable because this copy has no `.git` directory.
- Local FastAPI and dashboard browser flows were subsequently validated. Live AWS, Firebase, and Android builds remain unverified.

## Functional inventory

| Feature | Location | Status | Tests/evidence | Known issue | Required action |
|---|---|---|---|---|---|
| Detection configuration | `src/quakemesh_core/config.py` | implemented | core tests | values are environment-only | expose safe read-only config |
| Validation and replay protection | core validation, local/AWS ingress | implemented | unit/local tests | local and AWS error envelopes differ | define common envelope |
| H3 correlation and spatial diversity | core correlation/geo | implemented | synthetic tests; real H3 skipped | real adapter unverified here | rebuild environment and rerun |
| Event create/merge/resolve | core events, local service, Lambda | implemented | unit/concurrency tests | candidate/rejection state is not persisted | add run telemetry, not fake events |
| Detection footprint/frontier | core and event views | implemented | unit tests | dashboard shows latest event only | add event detail/map controls |
| SQLite local runtime | `local_runtime/` | implemented | local service tests | no reset, scenario, run, device, ACK, telemetry APIs | extend behind explicit demo controls |
| Virtual-phone fleet | `simulator/` | implemented | simulator tests | scenarios are hard-coded in `Fleet.scenario` | introduce catalog/run identity |
| Required scenarios | fleet and `experiments/scenarios.json` | implemented | unit-level behavior | degraded result is not summarized against expectation | record result and gates |
| Local launcher | `scripts/demo_local.ps1` | partially implemented | source inspection | child PowerShell argument construction is brittle; environment broken | use encoded safe launcher and add regression test |
| Dashboard | `dashboard/` | partially implemented | source inspection | single static page, polling only, no scenario control, limited states/accessibility | phased V2 information architecture |
| AWS IoT/Lambda/DynamoDB/API | `aws/` | implemented but unverified | contract tests | global names; no session identity/tags; scans in read API | session-scope and synth-test |
| AWS strict deletion | CDK stack/destroy scripts | broken for V2 | source inspection | S3 uses `RETAIN`; unmanaged logs; no verified cleanup | strict removal and verifier |
| Cloud-side expiry | none | placeholder | none | no scheduler cleanup path | exact-stack TTL controller |
| Android sensing | Android app | partially implemented | source inspection only | imperative UI; no app state, Demo Lab, alert history, ACK | Material 3 architecture and tests |
| Android FCM | messaging service | partially implemented | source inspection only | needs Firebase file and live validation | preserve optional configuration; label unverified |
| Schemas | `schemas/` | partially implemented | JSON parse contract | no event, scenario, stage, ACK, error schemas | add versioned contracts |
| Evidence export | simulator traces/upload | partially implemented | upload trace tests | no unified local review bundle/cleanup report | add exporter |
| Security/secret hygiene | `.gitignore`, scanner, scoped IoT policy | implemented | contract tests | API reads are public; demo write key is long-lived per stack | threat-model demo controls/session keys |

Status vocabulary is literal: “implemented” means code and relevant local tests exist; it does not imply live-service verification.

## Technical debt

- Dense one-line Python, Kotlin, and PowerShell reduces reviewability and makes error handling hard to audit.
- Local and Lambda flows duplicate ingestion/correlation persistence logic.
- `Fleet.scenario` is a monolithic name switch; `experiments/scenarios.json` is descriptive rather than executable.
- Dashboard HTML interpolates backend values with `innerHTML`; identifiers are constrained server-side, but safe DOM construction is preferable.
- Dashboard polls three endpoints every two seconds and only logs errors to the console.
- `demo_local.ps1` opens separate PowerShell windows and does not own or cleanly stop their processes.
- Most scripts assume `.venv\Scripts\python.exe` exists, but do not detect a stale launcher.
- CDK CLI is fetched through `npx --yes` at run time; there is no project lockfile.
- Stack, IoT policy, API key, and simulator thing names are global rather than session-scoped.
- CloudWatch log groups are implicit and therefore not explicitly retained/destroyed.
- S3 archive retention conflicts with strict ephemeral mode.
- AWS destroy discovers devices by a broad legacy prefix and does not produce a zero-resource report.
- Android uses platform views rather than Material 3/Compose, has no durable alert model, and has no tests or checked-in wrapper scripts.
- Generated `__pycache__`, `.pytest_cache`, `.ruff_cache`, a local database, and traces are present in this delivered copy; ignore rules exist but Git tracking cannot be checked.

## Dependency audit

| Area | Declared | Audit result |
|---|---|---|
| Python | `>=3.10`; FastAPI 0.141.1, Uvicorn 0.52.4, H3 4.5.0, boto3 1.43.89, AWS IoT SDK 1.31.0 | pins exist; prefer 3.12; environment must be recreated |
| Test/lint | pytest 9.1.1, Ruff 0.16.6 | pins exist; current validator cannot run from stale venv |
| Node/CDK | `npx aws-cdk@2.1140.0` | pinned command but no `package.json`/lockfile; convert to project-local CLI |
| CDK Python | `aws-cdk-lib==2.243.0`, constructs | separate venv; compatibility requires synth verification |
| Android | AGP 9.4.0, Gradle 9.6.0, Java 17, compile/target SDK 37, Firebase BoM 34.18.0 | declarations are mutually high/new and unverified; wrapper scripts and Google services file absent |
| Dashboard | Leaflet CDN, no build tool | easy startup, but CDN/network dependency and no frontend test harness |
| Firebase | optional SNS platform ARN and `google-services.json` | credentials intentionally absent; live delivery blocked by external setup |

## Immediate risks and priorities

1. Recreate the Python environment and preserve the 41-test baseline.
2. Fix and regression-test nested PowerShell argument passing.
3. Add authoritative scenario-run/stage telemetry before dashboard redesign.
4. Make every AWS resource session-owned before adding automatic deletion.
5. Never exercise live AWS or FCM without explicit credentials and user initiation.
