# QM-TRC-001 — Requirements Traceability

The project documentation rule is that critical requirements must map to implementation component, persistence, interface and verification.

| Requirement | Component(s) | Persistence | Interface | Verification |
|---|---|---|---|---|
| FR-ING-001 trigger ingest | validation, motion gate, local service, AWS ingress | Evidence | trigger schema / MQTT / POST | validation/motion tests, local E2E, AWS scenario |
| FR-ING-002 heartbeat | local service, AWS ingress | DeviceState | heartbeat schema / MQTT / POST | local E2E + AWS smoke |
| FR-ID-001 monotonic seq | SQLite repo, AWS conditional update | DeviceState | both write paths | `test_replay_rejected` + AWS replay run |
| FR-GEO-001 H3 canonicalization | `H3GeoIndex`, `canonicalize_trigger` | H3 cell attrs only | internal | real-H3 integration + privacy schema test |
| FR-COR-001 temporal window | `detect` + ingest clock-skew guard | Evidence TTL/time | internal | `test_stale_evidence_ignored`, `test_observation_clock_skew_guard` |
| FR-COR-002 distinct devices | `detect` | Evidence | internal | duplicate/isolated tests |
| FR-COR-003 distinct cells | `detect` | Evidence correlation cell | internal | same-cell test |
| FR-COR-004 spatial coherence | connected components | Evidence | internal | distant-component test |
| FR-EVT-001 confirmation | events core + correlator | Events | GET events | positive test + AWS distributed scenario |
| FR-EVT-002 merge/version | events core + correlator | Events version | event stream | merge/version test |
| FR-EVT-003 resolve | resolver | Events | scheduled internal | resolver/static + lifecycle AWS test |
| FR-ALT-001 footprint/frontier | core correlation/events | Events | GET event polygons | frontier test/dashboard |
| FR-ALT-002 target devices | local repo / dispatcher GSI query | DeviceState | alert path | local E2E + AWS dispatch |
| FR-ALT-003 alert idempotency | local unique alert key / AWS retry state machine + client event-ID dedupe | AlertDelivery | MQTT/FCM | alert key contract + repeated stream delivery run |
| FR-SIM-001 deterministic fleet | simulator | trace artifact | CLI | simulator tests |
| FR-SIM-002 truth isolation | simulator | trace only | trigger payload | `test_fleet_truth_not_in_payload` |
| FR-AND-001 Android sensing | `SensorService` | SharedPreferences seq only | HTTPS trigger | Android device/emulator test |
| FR-AND-002 FCM warning | messaging service, SNS | SNS endpoint ARN / alerts | FCM | physical/emulator FCM test |
| FR-OBS-001 dashboard | dashboard + read API | reads Events/Alerts | HTTP GET | JS syntax + manual live demo |
| NFR-SEC-001 IoT mTLS | provisioner + IoT policy | AWS IoT cert registry | MQTT/TLS | policy static test + real connection |
| NFR-SEC-002 gated HTTPS | CDK API methods | API Gateway key | x-api-key | infrastructure contract + 403 without key |
| NFR-PRIV-001 location minimization | canonicalization + schemas | H3 only | raw input transient | SQLite column test + DDB inspection |
| NFR-CON-001 versioned writes | correlator | Events.version | stream | merge test + conditional write source contract |
| NFR-COST-001 serverless | CDK | managed services | n/a | infrastructure audit |
| NFR-OBS-001 alarms | CDK | CloudWatch | console/API | stack inspection |
