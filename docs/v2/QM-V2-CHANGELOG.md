# QuakeMesh V2 changelog

## 2026-10-06 — local control-plane completion

- Converged dashboard and PowerShell scenario entry points on `ScenarioControlService` and authoritative run IDs.
- Added atomic one-active-run enforcement, strongly validated effective parameters, and deterministic degraded-network behavior.
- Partitioned devices, evidence, events, targeting, and alerts by physical/scenario provenance and scenario run ID.
- Added the complete truthful stage vocabulary, per-run ordering, SSE resume cursor, and REST recovery snapshots.
- Implemented V2 success/error envelopes, request IDs, local read/control endpoints, idempotent alert ACK, transactional scenario reset, and privacy-safe JSON evidence export.
- Replaced misleading local delivery status with `TARGETED` and retained event/run provenance on alerts.
- Rebuilt the dashboard as a feature-oriented React/strict-TypeScript/Vite application with bundled Leaflet and nine operational views.
- Added Vitest and Playwright coverage for negative/positive scenarios, ACK, export, disconnect retention, console cleanliness, and five responsive sizes.
- Expanded validation with PASS/SKIP reporting, targeted professional Ruff rules, schemas, npm lock verification, typecheck, lint, frontend tests/build, and optional browser E2E.
- Kept Android V2, AWS ephemeral sessions/deployment, and live FCM explicitly unverified.

## 2026-10-05

- Recorded the forensic V1 baseline, verification gaps, dependency state, and strict-ephemeral conflicts.
- Established controlled V2 requirements, architecture, lifecycle, UX, scenario, observability, API, test, security, runbook, and traceability documents.
- Replaced brittle nested PowerShell positional argument construction with encoded parameter splatting and added a binding smoke test.
- Added local scenario-run persistence, structured stage telemetry, a loopback-only scenario control API, and run-aware HTTP simulator transport.
- Added stale-venv recovery, detect-first Windows setup, and AWS account/cost safety guides.
- Corrected stale-launcher probing so Windows native-process errors enter the environment rebuild path.
- Isolated controlled-run evidence from physical evidence and made degraded-run result extraction tolerate intentionally dropped simulator records.
- Added a responsive dashboard Scenario Lab that starts real local runs and renders authoritative gate and stage telemetry.
- Rebuilt the local environment with Python 3.12, verified all required scenarios over HTTP, completed a browser interaction/console check, and recorded machine-readable evidence.
