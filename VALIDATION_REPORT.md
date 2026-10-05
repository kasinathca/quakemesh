# QuakeMesh V1 — Release Validation Report

**Release:** 1.0.1  
**Validation date:** 2026-09-13  
**Target cloud region:** `ap-south-1`  
**Packaging runtime:** Linux container, Python 3.13.5, Node.js 22.16.0


## Developer-PC H3 validation and validator hotfix (2026-09-13)

The Windows developer-PC setup completed successfully with Python 3.10.11 and installed the pinned H3 4.5.0 dependency. The full pytest suite then executed the real-H3 integration test and reported **40 passed**.
Release 1.0.1 adds two validator regression tests, so a fresh 1.0.1 developer-PC run with H3 installed is expected to report **42 passed** if all tests remain green.

The same run exposed a release-validation-script defect rather than a QuakeMesh source defect: Ruff had been invoked as `ruff check .`, which traversed `.venv` and reported third-party `site-packages` findings. Windows PowerShell 5.1 also continued after Ruff's non-zero exit code. Release 1.0.1 corrects both behaviors by:

- linting only QuakeMesh-owned Python paths (`src`, `local_runtime`, `simulator`, `aws`, `scripts`, `tests`);
- excluding `.venv` and `.venv-cdk` in Ruff configuration as defense in depth;
- wrapping native tool invocations so any non-zero `$LASTEXITCODE` terminates setup/validation;
- adding repository-contract regression tests for these validator guarantees.

The third-party Ruff findings from the original run are not treated as project defects because every reported path was inside `.venv/Lib/site-packages`.

## 1. Release decision

The source package is **ready for handoff as an implementation baseline**. The shared detector, local vertical slice, simulator, AWS source/infrastructure, dashboard, Android source, provisioning/teardown utilities, documentation, and validation automation are present in the release tree.

This report separates what was actually executed in the packaging environment from what necessarily remains to be executed on the developer's AWS/Firebase/Android environment. QuakeMesh remains an experimental academic prototype and is not validated for life-safety use.

## 2. Executed automated test suite

Command:

```text
pytest -q
```

Result:

```text
41 passed, 1 skipped
```

The single skip is `tests/test_h3_integration.py`. The packaging environment could not download/install the external `h3` wheel because outbound package resolution was unavailable. The pinned H3 version is `4.5.0`, and `scripts/setup.ps1` installs it before `scripts/validate.ps1` runs on the Windows development PC. That real-H3 test must execute rather than skip there.

The executed suite covers, among other cases:

- positive spatially diverse confirmation;
- isolated-device rejection;
- same-cell spatial-diversity rejection;
- stale evidence rejection;
- distant-component separation;
- per-device duplicate suppression;
- deterministic event keying;
- event merge/version behavior and stream-retry no-op behavior;
- event resolution;
- local alert uniqueness;
- raw-coordinate non-persistence in SQLite evidence;
- monotonic sequence replay rejection;
- defensive motion gate;
- non-finite/strict JSON-contract rejection;
- device/cloud clock-skew guard;
- concurrent local requests creating one authoritative event;
- deterministic simulator fleet behavior;
- simulator ground-truth isolation from detector payloads;
- packet-loss/jitter injection semantics;
- AWS IoT Thing-scoped policy source contract;
- API-key requirement on HTTPS writes;
- no VPC/EC2/RDS/ECS/EKS baseline constructs;
- secret-path `.gitignore` contract;
- safe AWS IoT simulator cleanup behavior;
- trace artifact validation/SHA-256 generation.

## 3. Executed local HTTP end-to-end scenarios

The real FastAPI HTTP server and the real simulator transport were executed together. Because the external H3 binary dependency was unavailable in this packaging environment, these HTTP E2E runs explicitly used the test-only deterministic `SyntheticGeoIndex`. They validate transport/concurrency/persistence/event/alert behavior but are **not claimed as H3 validation**.

| Scenario | Devices | Evidence persisted | Events | Alerts | Result |
|---|---:|---:|---:|---:|---|
| isolated | 25 | 1 | 0 | 0 | PASS — no confirmation |
| same-cell | 25 | 6 | 0 | 0 | PASS — no confirmation |
| distributed | 25 | 8 | 1 | 10 | PASS — exactly one confirmed event |
| degraded | 25 | 9 | 1 | 22 | PASS — confirmation survived deterministic loss/jitter seed |

The distributed live run was specifically used to detect and then regression-test a FastAPI concurrency race. The final implementation serializes the local correlation/event critical section, matching the correctness-first serialized AWS V1 correlator design.

## 4. Executed static/repository validation

Passed:

- Python byte-compilation across source and tests;
- repository structural audit;
- JSON schema/scenario parsing;
- Android XML parsing;
- Node.js syntax check for `dashboard/app.js`;
- repository secret scan;
- search for unresolved `TODO`, `FIXME`, `HACK`, or `XXX` markers.

The release secret scan found no embedded AWS access keys, private keys, or Google private-key material. Generated account/device credentials are excluded from the release and covered by `.gitignore`.

## 5. Dependency baseline verification

The release pins/documents the September 2026 baseline in `docs/DEPENDENCY_BASELINE.md`. Important current values include:

- H3 Python 4.5.0;
- FastAPI 0.141.1;
- Uvicorn 0.52.4;
- Boto3 1.43.89;
- AWS IoT Device SDK for Python v2 1.31.0;
- pytest 9.1.1;
- Ruff 0.16.6;
- `aws-cdk-lib` 2.268.0;
- AWS CDK Toolkit CLI 2.1140.0;
- Android Gradle Plugin 9.4.0;
- Gradle 9.6.0;
- Firebase Android BoM 34.18.0;
- google-services plugin 4.5.0.

## 6. Validation intentionally not claimed in packaging environment

The following require the user's environment/accounts and are therefore implementation-complete or source-complete but **not falsely marked as executed** here:

### Real H3 local run

Blocked here only by unavailable external package download. On the development PC:

```powershell
.\scripts\setup.ps1
.\scripts\validate.ps1
```

The H3 integration test should no longer skip.

### Ruff

Ruff is pinned in `requirements-dev.txt` and invoked by `scripts/validate.ps1`, but Ruff itself was not installed in the packaging container. The critical Python syntax/compile checks and pytest suite were executed independently here.

### AWS CDK synth/deploy

Not executed here because there are no user AWS credentials and external CDK package installation is unavailable. The repository contains:

- CDK stack source;
- Linux-compatible H3 Lambda-layer builder;
- pinned CDK Toolkit invocation;
- forced infrastructure-venv Python interpreter path;
- deploy/export/provision/run/upload/destroy scripts.

Run `aws sts get-caller-identity` and then `aws/scripts/deploy.ps1` on the user's PC.

### AWS IoT/SNS/FCM live delivery

Requires the user's AWS account, IoT certificates, Firebase project, and SNS platform application. MQTT simulator and FCM implementation paths are present but live cloud delivery is not claimed here.

### Android Gradle build/device validation

Requires Android Studio/JDK/SDK dependency downloads and the user's `google-services.json`. The release includes Android Gradle source and wrapper properties but not generated account credentials. Build/install on both an emulator and physical Android phone as described in `NEXT_STEPS.md`.

## 7. Release hardening completed before packaging

Notable defects caught and corrected during release validation include:

1. simulator observations were initially future-dated when concurrent synthetic propagation offsets were used;
2. network jitter was initially mixed into observation time instead of delivery delay;
3. concurrent FastAPI trigger requests could create duplicate local events;
4. runtime validation originally coerced values more permissively than the JSON schemas;
5. stale/high-sequence observations needed an explicit clock-skew guard;
6. ingest trusted client trigger labels without a defensive server-side motion gate;
7. simulator certificate teardown originally depended too heavily on local certificate files;
8. CDK execution needed to force the infrastructure virtual-environment interpreter;
9. immediate AWS event correctness could not rely on eventually consistent GSI propagation;
10. DynamoDB Stream replays needed true no-op event merges;
11. alert delivery needed retryable `DISPATCHING/FAILED/SENT` state rather than pre-send terminal claiming;
12. CDK Toolkit and Android build baselines were updated/pinned for reproducibility.

## 8. Integrity artifacts

`SOURCE_MANIFEST.txt` contains SHA-256 for every included release file except the manifest itself. The ZIP is accompanied by a separate `.sha256` checksum file.

## 9. Required first action after extraction

Do not deploy to AWS first. On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\validate.ps1
```

Proceed only after the full developer-PC validation is green and the real-H3 test executes rather than skips. Then follow `NEXT_STEPS.md` in order.
