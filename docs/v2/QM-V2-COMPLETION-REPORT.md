# QuakeMesh V2 local control-plane completion report

> Historical milestone document. Its dated limitations describe the state at each milestone and are preserved for traceability. The current final status is in `QM-V2-FINAL-DEMO-VALIDATION.md` and `QM-V2-FINAL-REVIEW-VERIFICATION.md`.

Report date: 2026-10-06 (Asia/Calcutta)

## Outcome

The V2 local control plane, authoritative scenario engine, observability contract, and professional dashboard are complete and verified on the current Windows host. This phase did not redesign Android or deploy AWS.

## Architecture decisions

- `ScenarioControlService` is the single controlled-run coordinator. Dashboard and PowerShell CLI start through `POST /v1/demo/scenario-runs`; tests invoke the same service. Controlled CLI traffic always has a run ID.
- SQLite `BEGIN IMMEDIATE` atomically creates a run and enforces one QUEUED/RUNNING scenario.
- Devices, evidence, events, targeting, and alerts are partitioned by physical/scenario provenance and optional scenario run ID.
- Catalog-owned parameter specifications normalize real fleet behavior and reject unknown, conflicting, mistyped, or out-of-range values.
- Stage records are persistent server telemetry. SSE streams their global cursor and per-run sequence; REST remains recovery truth.
- Local alert targeting records `TARGETED`, not delivery. ACK is idempotent and stage-producing only on the first transition.
- Reset is scenario-only and transactional. Export is privacy-safe JSON under the run's local artifact directory.
- Cancellation is omitted because the current synchronous fleet cannot guarantee safe interruption.
- The UI is a static React/strict-TypeScript/Vite build with bundled Leaflet and no CDN JavaScript/CSS dependency.

## Principal files changed

- Control plane: `local_runtime/app.py`, `contracts.py`, `errors.py`, `repository.py`, `scenario_catalog.py`, `scenarios.py`, `service.py`.
- Shared provenance model: `src/quakemesh_core/models.py`.
- Simulator/CLI: `simulator/fleet.py`, `simulator/transports.py`, `scripts/run_scenario.ps1`, `scripts/run_dashboard.ps1`, `scripts/run_e2e_backend.ps1`.
- Dashboard: `dashboard/package.json`, `package-lock.json`, TypeScript/Vite/ESLint/Playwright configuration, and feature modules under `dashboard/src/`.
- Tests/contracts: `tests/test_v2_control_plane.py`, updated dashboard/repository contracts, V2 schemas, `scripts/validate_schemas.py`, and expanded `scripts/validate.ps1`.
- Documentation: V2 API, scenario, observability, dashboard, architecture, traceability, changelog, README, and NEXT_STEPS.

## Verification results

`scripts/validate.ps1` completed with **14 PASS, 3 explicit SKIP, 0 FAIL**.

| Gate | Result |
|---|---|
| Python compilation | PASS |
| pytest | PASS — 76 tests (including live-lifecycle regression coverage for AWS scripts, MQTT SDK result shapes, Windows harness behavior, legacy migration, and exact-session cleanup) |
| Ruff critical repository rules | PASS |
| Ruff E4/E7/E9/F on V2-modified modules | PASS |
| secret scan | PASS |
| seven JSON schemas + V2 privacy/reference audit | PASS |
| PowerShell launch test | PASS |
| `npm ci --ignore-scripts` | PASS — 0 audit vulnerabilities reported by install |
| strict TypeScript | PASS |
| ESLint with zero warnings | PASS |
| Vitest | PASS — 2 files, 6 tests |
| production Vite build | PASS |
| Playwright | PASS — 2 tests |
| repository audit | PASS |

Python coverage verifies atomic concurrent-start rejection, dashboard/CLI record parity, physical/run isolation, spatially compatible run separation, truthful negative stages, deterministic degraded parameters, targeted alert provenance, idempotent ACK, reset refusal/preservation, export privacy, V2 envelopes/errors, and resumable stage ordering.

Browser E2E verifies:

1. isolated produces no confirmation and fails device diversity;
2. same-cell produces no confirmation and fails spatial diversity;
3. distributed confirms and exposes event, footprint, frontier, and alerts;
4. ACK reaches backend/dashboard;
5. run evidence exports;
6. API loss produces a disconnected state without deleting the prior snapshot;
7. no QuakeMesh-attributable browser console warning/error occurs;
8. 1280×720, 1366×768, 1440×900, 1920×1080, and 390×844 have no page-level horizontal overflow.

## Evidence locations

- `artifacts/e2e/distributed-scenario.png`
- `artifacts/e2e/narrow-overview.png`
- `artifacts/session_exports/local/<run_id>/run-evidence.json`
- `dashboard/playwright-report/` when the local report is retained

## Remaining risks

- Formal accessibility testing with assistive technology was not performed; automated semantic/focus/responsive checks are not a complete audit.
- Performance and load limits were not measured.
- SSE is an in-process local stream over SQLite; AWS must implement contract parity rather than reuse this transport directly.
- Local control is intentionally loopback-only and is not an internet-facing authorization design.
- Git history is established and synchronized with the GitHub `main` branch. The completed V2 local phase is recorded in commit `575ac25` (`Complete QuakeMesh V2 local phase`).

## Android V2 addendum — 2026-10-07

The subsequent Android milestone added typed V2 envelope/error handling, physical observation submission without scenario headers, observable foreground monitoring state, recurring heartbeats, a professional status UI, local-vs-corroborated state separation, local alert polling, `alert_id`-first FCM handling, and idempotent Android acknowledgement calls. The current Windows host completed 5 focused V2 envelope/error/alert JVM tests, debug compilation/APK assembly, and Android lint.

This historical 2026-10-07 boundary was superseded on 2026-10-19 by physical-device installation/launch, heartbeat/H3 and motion-evidence verification, notification preview tests, and a controlled labeled FCM receipt. The current limitations are recorded below.

## AWS and dashboard V2 addendum — 2026-10-08

The subsequent cloud milestone replaced the deployable V1 surface with a session-scoped V2 CDK stack and added the dashboard's runtime AWS adapter. CDK synthesis, Python tests, Ruff, strict TypeScript, ESLint, Vitest, the production dashboard build, and local Playwright coverage pass. The dashboard labels cloud mode as `AWS V2 Demo`, reads only real V2 health/device/event/alert responses, sends dashboard ACKs through the real API-key-gated route, and marks local-only controls unavailable instead of simulating their state.

This source, contract, synthesis, and local browser evidence was subsequently extended by the live lifecycle evidence below.

## Remaining unverified or limited behavior

- Broad Android device/emulator coverage, TalkBack, process recreation, and automatic heads-up behavior. The tested Android 15 handset did not show an automatic heads-up overlay; full-screen intent is intentionally disabled.
- Successful automatic expiry execution. The 2026-10-19 session remained active past expiry and required manual exact-session teardown.
- AWS reset/export controls; they are not part of the current cloud slice.
- Load/performance limits and final historical AWS billing after reporting delay.
- Authoritative physical-alert acknowledgement. Controlled FCM receipt was verified, but that test intentionally had no authoritative alert row and generated no ACK.

## Review harness addendum — 2026-10-08

The Windows review harness now includes one-time preparation, idempotent/recovering START, read-only STATUS, exact STOP, independent Local/AWS dashboard serving directories, optional Android installation, AWS smoke and authoritative warm-up gates, AWS CLI v2 selection, path-with-spaces-safe CDK execution, pre-deployment ownership metadata, and inventory-backed teardown verification. Preparation passed on the actual spaced repository path and `CDKToolkit` was bootstrapped in `ap-south-1`.

Direct authorization was subsequently provided for account `101541767123` in `ap-south-1`, and the live matrix below supersedes the earlier preparation-only limitation.

## Live AWS lifecycle addendum — 2026-10-08

The review harness is READY for the verified no-phone/no-FCM presentation scope. Two distinct default 25-device sessions, `qm-20261008-055623-f221` and `qm-20261008-060601-ec40`, each reached `QUAKEMESH REVIEW ENVIRONMENT READY`. Each run passed HTTPS heartbeat/trigger smoke, provisioned 25 session-owned IoT Things and certificates, delivered 50 MQTT records with zero simulator errors, produced one confirmed event and 17 alerts, passed authoritative warm-up, built the Android debug APK, and truthfully reported `NOT CONNECTED - APK READY`.

Re-running START during the first session reused the same session, stack, and three owned local processes. STATUS reported exactly one owned `CREATE_COMPLETE` stack, health PASS, 25 dynamic IoT Things, and live device/event/alert reads. Both STOP runs returned `CLEAN`; the verifier found the exact stack, Things, certificates, DynamoDB tables, Lambda functions/layer, alarms, log groups, IAM roles, IoT policy, Scheduler schedule, EventBridge rule, and API Gateway resources absent. A further STOP returned the clean already-stopped no-op result. Final STATUS reported zero owned QuakeMesh stacks, absent review state, restored local Android configuration, and ports 8000/8080/8081 stopped.

Shared `CDKToolkit` resources and content-addressed assets remain intentionally retained because they are not exclusively session-owned. FCM was not configured and was reported `NOT_APPLICABLE`; no physical phone was used. Automatic expiry cleanup remains unexecuted live.

## Final AWS, Android, and evaluation addendum — 2026-10-19

Session `qm-20261019-112257-b77a` used the repaired stream mappings and processing code. It persisted 25 scenario devices and nine scenario evidence rows, created one authoritative scenario event, generated and delivered 17 simulator alerts, and recorded zero correlator/dispatcher errors. The physical handset registered heartbeat/H3 state and an enabled session-owned SNS endpoint; a uniquely labeled controlled test proved FCM receipt, while physical motion evidence remained separate from the simulated event. Manual cleanup and a repeated read-only audit verified the stack and all 96 captured resource records absent. Automatic expiry did not complete on schedule.

The offline research evaluation completed 48 distinct seeded synthetic trials with the production detector and real H3: TP=24, TN=24, FP=0, FN=0, mean/median confirmation latency 513.75/469.5 ms, and 311/348 injected triggers delivered. These are controlled software-simulation results, not real-world earthquake-detection accuracy. Sanitized report data and figures are tracked under `results/offline-evaluation/`.

## Research-grade evaluation and wireless test addendum — 2026-10-22

The expanded deterministic benchmark completed all 320 planned trials with zero runner failures. Aggregate event-level results were TP=86, TN=151, FP=25, FN=58; the fixed held-out partition produced TP=18, TN=28, FP=5, FN=9. Exact metrics, Wilson/bootstrap intervals, parameter coverage, per-trial records, plots, and reproducibility metadata are tracked under `results/research-evaluation/` and documented in `QM-V2-RESEARCH-EVALUATION.md`.

The recorded-negative adapter evaluated 2,000 authentic UCI HAR smartphone accelerometer windows through the production Android motion feature/gate logic, using the dataset's subject-disjoint train/test split. The 1,000-window held-out partition produced 469 local motion-gate positives. This deliberately measures first-stage motion sensitivity on human activities; it does not claim 469 earthquake warnings because the cloud spatial-temporal quorum was not run on those isolated windows.

The implementation now includes a narrowly scoped operator-controlled wireless notification path. It uses a distinct secret credential, targets only a currently online notification-capable physical device in the exact session, resolves the SNS endpoint server-side, applies replay and rate-limit controls, sends an unmistakably non-authoritative data-only payload, and persists FCM-received, notification-posted, opened, or failed receipts. The Android client retains normal notification channels and no full-screen intent was added. This path is locally tested and CDK-synthesized; it was not deployed or exercised against AWS in this milestone.

Local verification completed with 108 passing Python tests, clean targeted Ruff and secret/schema checks, successful CDK synthesis, successful Android unit/lint execution across 36 Gradle tasks, seven passing dashboard unit tests, a production Vite build, and three passing Playwright tests. The research dashboard screenshot was visually inspected. No AWS deployment or paid cloud action was performed, and automatic expiry remains pending a future explicitly authorized live lifecycle test.
