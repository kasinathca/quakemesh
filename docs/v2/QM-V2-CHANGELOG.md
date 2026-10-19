# QuakeMesh V2 changelog

## 2026-10-19 — offline research evaluation and Android warning UX

- Added a deterministic independent-trial evaluator around the actual local detector and real H3, with external-only truth labels, loss, jitter, device-count, timing, and geographic variation.
- Added per-trial CSV/JSON, aggregate JSON/CSV/Markdown, labeled SVG figures, event-level confusion metrics, zero-denominator handling, Wilson intervals, deterministic latency bootstrap intervals, and explicit cloud/receipt non-observation fields.
- Measured 48 synthetic trials with TP 24, TN 24, FP 0, FN 0 and zero runner failures; documented the finite-sample confidence intervals and the limitation that these are not real-world earthquake-accuracy claims.
- Added an Evaluation / Metrics dashboard view with filters, plots, confusion matrix, actual generated data, and CSV/JSON/PNG exports while preserving Scenario Lab and AWS read-only behavior.
- Added silent monitoring, versioned authoritative-warning and controlled-preview channels, two original synthesized tones, high-priority heads-up presentation, and a dedicated warning activity with provenance and H3 context.
- Added a debug-only local preview which creates no cloud record and cannot ACK; preserved authoritative ACK, FCM deduplication/token handling, and polling fallback.
- Deliberately retained heads-up fallback rather than requesting restricted automatic full-screen behavior.
- Physically verified both labeled local preview channels on Android API 35, warning-screen navigation, background non-launch behavior, stable-ID deduplication, and unchanged authoritative alert state. Recorded that this Motorola build retained the HIGH-importance notifications in the shade and reported them non-interruptive instead of showing a heads-up overlay.

## 2026-10-19 — DynamoDB Streams startup-readiness repair

- Preserved the cleanly torn-down `qm-20261019-101849-9efb` failure evidence: AWS ingress produced 26 device and nine evidence rows, but no authoritative event or alert.
- Corrected both newly-created session stream mappings from `LATEST` to `TRIM_HORIZON`, retaining unchanged detector thresholds and existing replay idempotency.
- Added an exact-ARN, bounded `Enabled` readiness gate for evidence-to-correlator and event-to-dispatcher mappings before smoke or simulator ingestion.
- Added handler boundary logs and durable mapping/stream/Lambda/CloudWatch metric diagnostics before failed-session cleanup.
- Added offline regressions for activation delay, disabled/wrong mappings, timeout diagnostics, INSERT handling, replay, retries, dispatch, real H3 correlation and START cleanup ordering.
- Made START validate the reusable `QuakeMesh-FCM-Demo` ARN against the authenticated account/region, export it through `QM_SNS_PLATFORM_APPLICATION_ARN`, and pass it explicitly into deployment.
- Live-verified the repair in session `qm-20261019-112257-b77a`: both mappings Enabled/OK, 25 scenario devices, nine scenario evidence rows, one confirmed event, 17 alert rows, 17 simulator receipts, and zero Lambda errors.
- Verified an AWS-configured physical handset heartbeat/H3 registration, enabled session-owned SNS endpoint, uniquely labeled controlled FCM receipt, and independently isolated physical motion evidence.
- Fixed diagnostic CLI serialization of boto3 timestamps and made local correlation deterministic for reverse-timestamp arrivals; the full suite now has 98 passing tests.

## 2026-10-08 — live AWS lifecycle verification

- Completed two distinct default 25-device START→READY→STOP/CLEAN sessions in account `101541767123`, region `ap-south-1`, plus active-session START reuse and already-stopped STOP.
- Verified HTTPS smoke, 50-record MQTT distributed warm-up with zero errors, one confirmed event, 17 alerts, live status reads, Android APK assembly, exact resource inventory teardown, zero owned stacks, and stopped local ports.
- Hardened AWS profile propagation, IoT ownership/provisioning, Lambda layer imports, IoT SQL aliases, simulator SDK future handling, teardown verification, Windows process/state handling, optional ADB detection, and workspace-owned pytest temp usage based on live findings.
- Retained shared `CDKToolkit` and content-addressed assets by design; physical Android, FCM delivery, and automatic expiry execution remain separate unverified scopes.

## 2026-10-08 — AWS V2 foundation

- Replaced the fixed-name/retained V1 deployment surface with session-scoped V2 stack names, tags, expiry metadata, policies, topics, logs, and destroy-on-teardown state.
- Added V2 AWS envelopes, request IDs, stable errors, device/event/alert reads, physical HTTPS ingress, idempotent Android ACK, and safe alert views.
- Partitioned cloud device/evidence/correlation/event/targeting data by physical or scenario provenance and run/session ID.
- Added structured API, persistence, correlation, event, delivery, and acknowledgement CloudWatch log stages without logging secrets or raw coordinates.
- Added exact-session deploy, simulator provisioning, MQTT scenario, smoke, teardown, and zero-owned-resource verification tooling.
- Updated FCM/MQTT alerts to carry `alert_id`, event identity/version/status, device identity, and timestamps.
- Made FCM v1 delivery high-priority and data-only so Android's messaging service receives the authoritative alert payload in foreground and background execution paths; added a payload contract test.
- Added AWS V2 contract tests and locally synthesized the CDK template; the later live-lifecycle section above records the subsequent deployment evidence.
- Added runtime-configured dashboard AWS mode for real cloud device/event/alert/ACK reads, explicit environment/session/region status, and honest unavailable states for local-only controls.
- Added a one-time EventBridge Scheduler expiry backstop whose cleanup Lambda verifies exact session ownership, refuses shared/unexpected IoT credentials, and requests deletion of only its own stack.

## 2026-10-07 — Android V2 foundation

- Added typed V2 networking/errors while retaining schema `1.0` observation payloads and physical no-run-header provenance.
- Added observable foreground monitoring state, recurring heartbeats, local motion state, alert polling, alert-ID FCM handling, and idempotent ACK.
- Replaced the primitive screen with a professional research-status interface that separates local motion from cloud-corroborated events.
- Added debug-only emulator loopback networking while keeping release cleartext disabled.
- Verified debug APK assembly and Android lint; emulator, physical device, and live FCM remain unverified.
- Added five JVM tests for V2 success envelopes, structured/fallback errors, observation receipts, and authoritative alert/ACK identity.

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
