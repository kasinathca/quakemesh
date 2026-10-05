# QuakeMesh Controlled Documentation Index

**Baseline:** V1 academic prototype  
**Cloud region:** `ap-south-1`  
**Status:** implementation baseline  
**Scope rule:** this set ends at `QM-OPS-001`; do not create endless new design documents unless a controlled update is required.

## Reading order

1. `AI_READER.md` — compact project truth for humans or another AI assistant.
2. `QM-SRS-001_REQUIREMENTS.md` — controlled functional/non-functional requirements and exclusions.
3. `QM-ARCH-001_ARCHITECTURE.md` — end-to-end architecture and runtime flows.
4. `QM-GEO-001_H3_MODEL.md` — H3 canonicalization, Detection Footprint and Warning Frontier.
5. `QM-DATA-001_DATA_MODEL.md` — local SQLite and AWS DynamoDB state models.
6. `QM-API-001_INTERFACES.md` — message/API contracts.
7. `QM-SEC-001_SECURITY_PRIVACY.md` — trust boundaries, mTLS, demo API-key boundary and location minimization.
8. `QM-AWS-001_INFRASTRUCTURE.md` — deployed AWS resources and IAM intent.
9. `QM-SIM-001_SIMULATOR.md` — deterministic virtual-phone experiment harness.
10. `QM-AND-001_ANDROID.md` — physical/emulated Android client.
11. `QM-TEST-001_TEST_STRATEGY.md` — executable validation strategy.
12. `QM-EXP-001_EXPERIMENT_PLAN.md` — experiment protocol and evidence collection.
13. `QM-TRC-001_TRACEABILITY.md` — requirements → components → persistence → interfaces → tests.
14. `QM-OPS-001_OPERATIONS.md` — setup, run, deploy, observe and teardown.

## Architecture decision records

- `ADRs/ADR-001-H3.md`
- `ADRs/ADR-002-SERVERLESS-AWS.md`
- `ADRs/ADR-003-HYBRID-TRANSPORT.md`
- `ADRs/ADR-004-NO-MAGNITUDE-EPICENTRE.md`
- `ADRs/ADR-005-CORRELATOR-SERIALIZATION.md`

## Controlled terminology

**Trigger:** a device-local motion observation submitted for cloud corroboration. A trigger is not an earthquake declaration.

**Evidence:** a validated trigger after latitude/longitude is canonicalized to H3 identifiers.

**Detection Footprint:** the distinct coarse H3 cells that actually contributed evidence to a confirmed QuakeMesh event.

**Warning Frontier:** the configurable H3 ring surrounding the Detection Footprint used to choose demonstration alert recipients. It is not an epicentre estimate, seismic wavefront, magnitude contour, or physically predicted arrival-time boundary.

**Confirmed event:** a QuakeMesh application state meaning configured temporal, device-diversity, cell-diversity and spatial-coherence thresholds were satisfied. It is not an authoritative earthquake declaration.
