# QuakeMesh V2 software requirements

## Scope

QuakeMesh is an experimental distributed cloud/IoT motion-corroboration prototype. Confirmation means only that configured experimental gates passed. It does not predict earthquakes, estimate magnitude or epicentre, issue an official warning, or provide a life-safety guarantee.

## Functional requirements

- **V2-FR-001** Ingest validated heartbeat and trigger observations without persisting raw coordinates beyond canonicalization needs.
- **V2-FR-002** Reject replayed/out-of-order device sequences and observations outside the clock-skew bound.
- **V2-FR-003** Confirm only when recency, unique-device, coarse-cell diversity, and spatial-coherence gates pass.
- **V2-FR-004** Preserve isolated and same-cell rejection and distributed confirmation; degraded is evaluated from surviving evidence.
- **V2-FR-005** Assign each scenario execution a unique run ID and record source, mode, parameters, timestamps, status, expected result, observed result, and failure detail.
- **V2-FR-006** Emit truthful stage events for request, fleet preparation, injection, ingress, validation, storage, correlation, event transition, targeting, dispatch, and acknowledgement.
- **V2-FR-007** Permit scenario control through local/AWS CLI and authenticated demo APIs used by dashboard and Android.
- **V2-FR-008** Expose events, devices, alerts, scenario runs, stage events, configuration, and safe build/session metadata through parity contracts.
- **V2-FR-009** Show current runtime state, map footprint/frontier, gate outcomes, timeline, and logs without client-side fabrication.
- **V2-FR-010** Preserve Android sensor monitoring and add Demo Lab, experimental-warning history/detail, and acknowledgement.
- **V2-FR-011** Create AWS environments with a unique session ID, expiry, and ownership tags.
- **V2-FR-012** Stop or expire a session by deleting only resources proven to belong to that session and emit local cleanup reports.
- **V2-FR-013** Export non-secret review evidence locally before strict cloud teardown.
- **V2-FR-014** Support reset of experiment data without conflating reset with infrastructure deletion.

## Non-functional requirements

- **V2-NFR-001 Truthfulness:** unknown, unavailable, skipped, and unverified states are displayed as such.
- **V2-NFR-002 Safety:** one device can never confirm an event; strict cleanup never selects resources by a broad name alone.
- **V2-NFR-003 Reproducibility:** scenario seed and parameters are stored with results.
- **V2-NFR-004 Idempotency:** replayed observations, stream records, ACKs, starts, stops, and cleanup retries have deterministic outcomes.
- **V2-NFR-005 Accessibility:** keyboard operation, visible focus, semantic labels, non-color status cues, contrast, and 48dp Android targets.
- **V2-NFR-006 Performance:** no sub-second blind polling; measured timings are labeled with source and sample context.
- **V2-NFR-007 Security/privacy:** least privilege, no secrets in source/artifacts, coarse spatial persistence, protected demo controls.
- **V2-NFR-008 Portability:** local mode requires no AWS account; Windows setup detects before installing.
- **V2-NFR-009 Maintainability:** shared domain logic, versioned contracts, small modules, and automated gates.
- **V2-NFR-010 Cost control:** no EC2, RDS, NAT Gateway, ECS, EKS, custom VPC, or intentionally retained session storage in strict mode.

## Acceptance rule

A requirement is `VERIFIED` only when its traceability row names repeatable evidence. Code presence alone is `IMPLEMENTED` or `PARTIALLY VERIFIED`.
