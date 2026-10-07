# QuakeMesh V2 requirements traceability

Status reflects evidence generated on 2026-10-06. “Verified locally” never implies Android, AWS, or live FCM verification.

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
| V2-FR-009 dashboard | React/TypeScript/Vite modules + runtime Local/AWS adapter and capability states | unit, build, local E2E, responsive screenshots | VERIFIED locally; live AWS data not verified |
| V2-FR-010 Android V2 | typed V2 client, observable monitoring state, professional status UI, local alert polling, alert-ID FCM parsing, Android ACK | Gradle debug compile/APK assembly/lint | PARTIALLY VERIFIED; emulator, physical device, traffic, and FCM not run |
| V2-FR-011 AWS session ownership | session stack name, tags, expiry metadata, scoped names/topics, destroy policies | source tests + CDK synth | IMPLEMENTED; not live-deployed |
| V2-FR-012 AWS teardown/verifier | metadata/account guard, exact IoT prefix cleanup, exact stack destroy, tag/Thing/stack verification | source tests + script audit | IMPLEMENTED; live CLEAN report not verified |
| V2-FR-013 local evidence export | ScenarioControlService export | privacy/export test + browser E2E | VERIFIED locally |
| V2-FR-014 local reset | transactional scenario-only reset | active refusal/physical preservation tests | VERIFIED locally |
| V2-NFR-001 truthful status | TARGETED alerts, gate/status vocabulary | API, service, E2E assertions | VERIFIED locally |
| V2-NFR-002 safety | negative gates + provenance isolation | isolated/same-cell/cross-run tests | VERIFIED locally |
| V2-NFR-003 reproducibility | seed + effective parameters | degraded deterministic test | VERIFIED locally |
| V2-NFR-004 idempotency/concurrency | replay, ACK, atomic active-run lock | Python concurrency/ACK tests | VERIFIED locally |
| V2-NFR-005 accessibility/responsiveness | semantic navigation/tables/status/focus | automated viewport/overflow checks | PARTIALLY VERIFIED; formal accessibility audit not run |
| V2-NFR-006 performance | bounded lists, 5 s recovery poll, SSE | functional only | NOT LOAD-VERIFIED |
| V2-NFR-007 security/privacy | loopback controls, safe reads/exports, secret scan | schema/privacy/secret tests | VERIFIED locally for this scope |
| V2-NFR-008 portability | Python + static dashboard launch scripts | Windows local validation | VERIFIED on current Windows host |
| V2-NFR-009 maintainability | feature modules, contracts, targeted professional lint | typecheck/lint/tests | VERIFIED locally |
| V2-NFR-010 cloud cost control | no cloud action in phase | none | NOT VERIFIED |
