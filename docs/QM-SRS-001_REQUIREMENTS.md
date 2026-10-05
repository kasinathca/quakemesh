# QM-SRS-001 — Software Requirements Specification

## 1. System objective

Build an experimentally testable cloud-native prototype that ingests independent phone motion triggers, converts device positions to H3 spatial identities, suppresses isolated/localized false positives, creates a cloud-authoritative event only after configured corroboration rules are satisfied, and dispatches warnings to devices in a derived H3 target region.

## 2. Actors

- **Python virtual phone** — deterministic experiment client hosted on the single development PC.
- **Android phone/emulator** — sensor client using accelerometer, location and FCM.
- **AWS IoT Core** — authenticated MQTT ingress/egress broker.
- **QuakeMesh cloud backend** — validation, evidence persistence, correlation, authoritative event state and dispatch.
- **Operator/dashboard** — read-only observation of events and deliveries.

## 3. Functional requirements

| ID | Requirement | Acceptance intent |
|---|---|---|
| FR-ING-001 | Accept versioned motion-trigger messages. | Malformed or unsupported payloads are rejected. |
| FR-ING-002 | Accept device heartbeat/presence messages separately from triggers. | Presence does not create evidence. |
| FR-ID-001 | Reject non-monotonic sequence numbers per device. | Replay/duplicate does not increase evidence. |
| FR-GEO-001 | Canonicalize latitude/longitude to an H3 device cell and correlation parent cell. | Persistent evidence contains cell IDs, not raw coordinates. |
| FR-COR-001 | Correlate evidence only inside a configured temporal window. | Stale evidence cannot confirm a new event. |
| FR-COR-002 | Require a minimum count of distinct devices. | Repeated messages from one device cannot satisfy count. |
| FR-COR-003 | Require a minimum count of distinct correlation H3 cells. | Many devices in one cell are insufficient. |
| FR-COR-004 | Require spatial coherence rather than mixing arbitrarily distant evidence. | Unrelated distant components remain separate. |
| FR-EVT-001 | Create a cloud-authoritative confirmed event after requirements are satisfied. | Event has stable ID, version and timestamps. |
| FR-EVT-002 | Merge subsequent compatible evidence into the active event. | Footprint/device/evidence sets expand monotonically while active. |
| FR-EVT-003 | Resolve an inactive confirmed event automatically. | Scheduler transitions stale confirmed events to RESOLVED. |
| FR-ALT-001 | Derive Detection Footprint and Warning Frontier from H3 cells. | Frontier excludes footprint and is reproducible. |
| FR-ALT-002 | Target recently seen devices in footprint/frontier cells. | Targeting uses H3 state, not stored raw coordinates. |
| FR-ALT-003 | Avoid repeat warning delivery to a device for the same event. | Alert-delivery conditional record is keyed by event+device. |
| FR-SIM-001 | Run deterministic multi-phone scenarios on one PC. | Fixed seed produces repeatable placement/fault decisions. |
| FR-SIM-002 | Keep simulator ground truth out of transmitted detector payloads. | Truth is present only in experiment trace. |
| FR-AND-001 | Android client shall monitor real accelerometer/location data and submit only local triggers. | No manual “earthquake confirmed” control exists. |
| FR-AND-002 | Android client shall receive FCM warning messages when Firebase/SNS is configured. | High-importance warning notification is displayed. |
| FR-OBS-001 | Dashboard shall show event state, H3 footprint/frontier and alert records. | Local and AWS GET API contracts are consumable. |

## 4. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-SEC-001 | AWS IoT simulator identity uses X.509/mTLS and Thing-scoped IoT policy resources. |
| NFR-SEC-002 | HTTPS write fallback is not anonymous; API Gateway requires a controlled-demo API key. |
| NFR-PRIV-001 | QuakeMesh application persistence does not retain raw latitude/longitude. |
| NFR-CON-001 | Event updates use a version field and conditional writes. |
| NFR-COST-001 | V1 uses managed/serverless AWS services and no VPC/NAT/EC2/RDS. |
| NFR-OBS-001 | Lambda errors have CloudWatch alarms; Lambda tracing is enabled. |
| NFR-REP-001 | Simulation runs emit machine-readable trace artifacts. |
| NFR-PORT-001 | Local demonstration runs on one Windows PC using Python 3.10+; Python 3.12 is recommended for parity with Lambda. |

## 5. Explicit non-requirements

- seismological magnitude estimation;
- epicentre/hypocentre localization;
- public emergency broadcast authority;
- guaranteed delivery/latency suitable for life safety;
- malicious-device consensus/reputation;
- identity/account system for human users;
- iOS/macOS emulation.

## 6. Safety/claims constraint

Documentation and UI must use wording such as “corroborated ground-motion evidence” and “QuakeMesh event.” They must not present the prototype as an official earthquake detector or promise safety-critical warning performance.
