# QuakeMesh V2 requirements traceability

Status reflects evidence generated through 2026-10-24. Local tests, synthetic evaluation, live AWS processing, physical Android behavior, wireless FCM delivery, and real-world seismological validity remain distinct evidence scopes.

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| V2-FR-001 validation/canonicalization | shared core + local service | Python validation/H3 tests | VERIFIED locally |
| V2-FR-002 replay/time guards | repository/service | replay, skew, stage tests | VERIFIED locally |
| V2-FR-003 correlation | shared detector | positive, isolated, same-cell, coherence tests | VERIFIED locally |
| V2-FR-004 simulator scenarios | Fleet + normalized catalog | deterministic parameter and browser scenario tests | VERIFIED locally |
| V2-FR-005 authoritative run model | ScenarioControlService + atomic SQLite run creation | dashboard/CLI parity and concurrency tests | VERIFIED locally |
| V2-FR-006 stage telemetry | scenario service + detector stages | negative-stage, sequence, SSE-resume tests | VERIFIED locally |
| V2-FR-007 local control API | FastAPI V2 envelope/endpoints | API integration and browser tests | VERIFIED locally |
| V2-FR-008 local parity reads | typed local endpoints | API surface integration test | VERIFIED locally |
| V2-FR-009 dashboard | React/TypeScript/Vite modules + Local/AWS adapters, cloud Scenario Lab/history/reset, Evaluation/Metrics exports | 7 unit tests, build, 3 local E2E tests, live AWS scenario operation/reads | VERIFIED locally and in final live AWS session |
| V2-FR-010 Android V2 | typed client, monitoring, alert-ID FCM, warning/demo channels, full-screen WarningActivity, attention service, dedupe, receipts and guarded ACK | JVM tests, Firebase APK/build/lint, heartbeat/H3, USB-disconnected authoritative FCM, unlocked heads-up, locked full-screen, stop/ACK | VERIFIED for named handset/session; broader device/accessibility coverage pending |
| V2-FR-011 AWS session ownership | session stack name, tags, expiry metadata, scoped names/topics, destroy policies, one-time Scheduler cleanup with ownership refusal checks | source tests, synth, live sessions, final inventory audit | VERIFIED live for manual lifecycle; automatic expiry did not complete on time |
| V2-FR-012 AWS teardown/verifier | account/tag guard, exact IoT/SNS cleanup including post-destroy endpoint-race closure, exact stack destroy, concrete inventory verification | final inventory-backed CLEAN plus fresh 2026-10-24 audit | VERIFIED live for manual teardown |
| V2-FR-013 local evidence export | ScenarioControlService export | privacy/export test + browser E2E | VERIFIED locally |
| V2-FR-014 local reset | transactional scenario-only reset | active refusal/physical preservation tests | VERIFIED locally |
| V2-NFR-001 truthful status | TARGETED alerts, gate/status vocabulary | API, service, E2E assertions | VERIFIED locally |
| V2-NFR-002 safety | negative gates + provenance isolation | isolated/same-cell/cross-run tests | VERIFIED locally |
| V2-NFR-003 reproducibility | seeds, effective parameters, independent trial databases, real H3 | 48 distinct seeded trials, CSV/JSON, figures, rerun command | VERIFIED for controlled synthetic software evaluation |
| V2-NFR-004 idempotency/concurrency | replay, ACK, atomic active-run lock | Python concurrency/ACK tests | VERIFIED locally |
| V2-NFR-005 accessibility/responsiveness | semantic navigation/tables/status/focus | automated viewport/overflow checks | PARTIALLY VERIFIED; formal accessibility audit not run |
| V2-NFR-006 performance | bounded lists, 5 s recovery poll, SSE | functional only | NOT LOAD-VERIFIED |
| V2-NFR-007 security/privacy | loopback controls, safe reads/exports, secret scan | schema/privacy/secret tests | VERIFIED locally for this scope |
| V2-NFR-008 portability | clickable review wrappers, explicit AWS CLI v2 resolution, path-safe CDK virtualenv invocation, independent dashboard copies | preparation, synth, and complete live lifecycle from spaced Windows path | VERIFIED live on current Windows host |
| V2-NFR-009 maintainability | feature modules, contracts, targeted professional lint | typecheck/lint/tests | VERIFIED locally |
| V2-NFR-010 cloud cost control | exact ownership, expiry guard, manual STOP, inventory verifier | final zero-stack/zero-port status and 96-resource absence audit | VERIFIED for manual cleanup; automatic expiry issue and delayed billing remain outstanding |
