# QuakeMesh V2 local control-plane completion report

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
| pytest | PASS — 66 tests (previous local coverage retained; AWS lifecycle/FCM contract tests added) |
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

This does not revise or weaken the local control-plane evidence above. Emulator/physical-device execution, real Android-to-FastAPI traffic, and live FCM remain unverified.

## AWS and dashboard V2 addendum — 2026-10-08

The subsequent cloud milestone replaced the deployable V1 surface with a session-scoped V2 CDK stack and added the dashboard's runtime AWS adapter. CDK synthesis, Python tests, Ruff, strict TypeScript, ESLint, Vitest, the production dashboard build, and local Playwright coverage pass. The dashboard labels cloud mode as `AWS V2 Demo`, reads only real V2 health/device/event/alert responses, sends dashboard ACKs through the real API-key-gated route, and marks local-only controls unavailable instead of simulating their state.

This is source, contract, synthesis, and local browser evidence. No live AWS endpoint or cloud record was available on this host, so deployment behavior and the dashboard's live AWS data path remain unverified.

## Explicitly not verified

- Android emulator or physical-device UI/sensor/location/network behavior; build and lint are verified separately in the addendum.
- AWS live deployment, endpoint behavior, account ownership, automatic expiry execution, or live teardown. Session ownership, strict manual/automatic cleanup source, V2 envelopes/provenance/telemetry, and CDK synthesis are verified separately as of 2026-10-08.
- AWS reset/export controls; they are not part of the current cloud slice.
- AWS IoT delivery, DynamoDB records, CloudWatch behavior, or costs.
- Live FCM delivery or physical phone receipt.

Those areas remain future phases and must not be inferred from the local completion result.
