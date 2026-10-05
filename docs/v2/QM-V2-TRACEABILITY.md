# Requirements traceability

| Requirement | Design component | Source | Test/evidence | Status |
|---|---|---|---|---|
| V2-FR-001 | validation/canonicalization | core validation, correlation, repositories | raw-coordinate and validation tests | VERIFIED locally |
| V2-FR-002 | sequence/time guards | local service/repository, AWS ingress | replay and clock-skew tests | VERIFIED locally; AWS not live-verified |
| V2-FR-003 | correlation engine | core correlation | positive/negative/spatial tests | VERIFIED with synthetic geo; real H3 skipped |
| V2-FR-004 | scenario fleet | simulator fleet | simulator/core tests | PARTIALLY VERIFIED; no full HTTP E2E |
| V2-FR-005 | run model | local repository/scenarios | scenario-run tests | IMPLEMENTED locally; HTTP E2E pending |
| V2-FR-006 | stage telemetry | local service/scenarios | repository round-trip test | PARTIALLY VERIFIED |
| V2-FR-007 | control API | local app | source and unit inspection | IMPLEMENTED locally; runtime E2E pending |
| V2-FR-008 | parity reads | local app/AWS API | source inspection | PARTIALLY IMPLEMENTED |
| V2-FR-009 | dashboard | static dashboard Scenario Lab | dashboard contract + local HTTP evidence | PARTIALLY VERIFIED |
| V2-FR-010 | Android | Android sources | source inspection | PARTIALLY IMPLEMENTED; build unverified |
| V2-FR-011 | session ownership | ephemeral design | none | NOT IMPLEMENTED |
| V2-FR-012 | teardown/verifier | legacy destroy | source inspection | NOT IMPLEMENTED for V2 strict mode |
| V2-FR-013 | evidence export | trace upload | unit tests for trace | PARTIALLY IMPLEMENTED |
| V2-FR-014 | reset | design only | none | NOT IMPLEMENTED |
| V2-NFR-001 | truthful status | all UX specs | audit terminology | PARTIALLY IMPLEMENTED |
| V2-NFR-002 | safety | core + cleanup design | single-device test | PARTIALLY VERIFIED |
| V2-NFR-003 | reproducibility | simulator seed/trace | simulator tests | PARTIALLY VERIFIED |
| V2-NFR-004 | idempotency | repository/event logic | replay/merge/concurrency tests | PARTIALLY VERIFIED |
| V2-NFR-005 | accessibility | dashboard/Android UX | none | NOT VERIFIED |
| V2-NFR-006 | performance | observability | none | NOT VERIFIED |
| V2-NFR-007 | security/privacy | security design | secret/policy tests | PARTIALLY VERIFIED |
| V2-NFR-008 | portability | local runtime/setup | baseline tests | PARTIALLY VERIFIED; environment broken |
| V2-NFR-009 | maintainability | shared core/contracts | source inspection | PARTIALLY VERIFIED |
| V2-NFR-010 | cost control | CDK/lifecycle | no-VPC contract test | PARTIALLY VERIFIED; retained S3 violates strict mode |
