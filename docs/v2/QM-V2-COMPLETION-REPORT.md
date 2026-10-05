# QuakeMesh V2 completion report

Report date: 2026-10-06 (Asia/Calcutta). This is an interim evidence report; QuakeMesh V2 is **not complete**.

## Executive status

| Area | Status | Evidence |
|---|---|---|
| V1 domain behavior | VERIFIED locally | 50 tests; real H3 adapter included |
| Dashboard launcher regression | VERIFIED locally | nested PowerShell integer-binding smoke test |
| Scenario run/state model | VERIFIED locally | persistence/unit tests and live HTTP runs |
| Required scenarios | VERIFIED locally | isolated rejected, same-cell rejected, distributed confirmed, degraded conditionally confirmed |
| Stage telemetry | PARTIALLY VERIFIED | live schema/motion/evidence/correlation/event stages in local mode |
| Dashboard Scenario Lab | PARTIALLY VERIFIED | browser start-to-completion flow, responsive narrow view, zero console warnings/errors |
| Full dashboard information architecture | NOT VERIFIED | remaining Events/Devices/Infrastructure/Experiments/Session views not implemented |
| Android V2 | NOT VERIFIED | existing sensor/FCM source only; no build or redesign evidence |
| AWS strict ephemeral session | NOT VERIFIED | design documents exist; legacy retained S3 and non-session stack remain |
| AWS live integration | BLOCKED BY EXTERNAL CREDENTIAL | no authenticated account/session was requested or used |
| Firebase live delivery | BLOCKED BY EXTERNAL CREDENTIAL | no Firebase project/device authorization |
| Git hygiene | NOT VERIFIED | this delivered checkout has no `.git` metadata |

## Implemented in this increment

- Controlled V2 audit, requirements, architecture, lifecycle, UX, scenario, observability, API, test, security, runbook, traceability, first-run, AWS account, and cost-safety documents.
- Safe nested PowerShell launching through encoded parameter splatting.
- Detect-first Windows setup and stale-venv recovery with native Python 3.12.
- Scenario run/stage SQLite schema, deterministic run IDs, required catalog, loopback-only start/read API, and run-aware simulator transport.
- Separation of controlled-run evidence from physical evidence.
- Responsive Scenario Lab with authoritative status, observed/expected result, gate counts, and stage timeline.

## Verification evidence

`scripts/validate.ps1` result:

```text
Python compilation                  PASSED
pytest                              50 passed
Ruff critical checks               PASSED
secret scan                         PASSED
PowerShell process-launch smoke     PASSED
repository structural audit         PASSED
```

Local HTTP results with Python 3.12, FastAPI, SQLite, and H3 4.5.0:

| Scenario | Expected | Observed | Result |
|---|---|---|---|
| isolated | NO_CONFIRMATION | NO_CONFIRMATION | VERIFIED |
| same-cell | NO_CONFIRMATION | NO_CONFIRMATION | VERIFIED |
| distributed | CONFIRMATION | CONFIRMATION | VERIFIED |
| degraded, seed 42 | CONDITIONAL | CONFIRMATION | VERIFIED for this deterministic run |

Browser validation started a distributed run from the UI and visibly reached `COMPLETED`, `CONFIRMATION`, 8/4 unique devices, 4/3 distinct H3 cells, an event footprint/frontier, and local alert records. Browser console warning/error query returned an empty list.

## Known limitations and next engineering gates

1. Implement remaining dashboard views, error-envelope parity, reset/export, and automated browser E2E.
2. Redesign/build/test the Android app and implement ACK contracts.
3. Replace the legacy AWS stack with session identity, ownership tags, strict deletion, explicit logs, Scheduler TTL cleanup, and a zero-resource verifier.
4. Add project-local locked CDK tooling and synth/policy tests.
5. Perform live AWS and FCM validation only with user-provided authentication and explicit cloud-session start.

## Current commands

```powershell
.\scripts\setup_windows.ps1
.\scripts\validate.ps1
.\scripts\demo_local.ps1 -Scenario distributed -Devices 25
```

The V2 `session_start.ps1`/`session_stop.ps1` commands remain design targets and must not be presented as available until implemented and verified.
