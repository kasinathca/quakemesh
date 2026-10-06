# QuakeMesh V2 scenario engine

## Authority and state policy

Dashboard, `scripts/run_scenario.ps1`, tests, and future Android clients start runs through `ScenarioControlService`. `ScenarioRunner` behavior is implemented by that service's `execute_run`; the API and CLI do not own alternate state machines. CLI simulation is therefore scenario evidence with a run ID, never physical/unowned evidence.

SQLite creates a run and its first stage under `BEGIN IMMEDIATE`. The default local policy is one QUEUED or RUNNING controlled run. A concurrent request receives HTTP 409 `SCENARIO_ALREADY_RUNNING`.

Run states are `QUEUED`, `RUNNING`, `COMPLETED`, and `FAILED`. Run IDs use `QMR-<UTC compact timestamp>-<random suffix>`.

## Provenance isolation

Authoritative devices, evidence, events, and alerts carry `provenance_type` (`physical` or `scenario`) and optional `scenario_run_id`.

- Physical evidence correlates and merges only with physical records.
- Scenario evidence correlates, merges, targets, and alerts only inside its own run ID.
- Temporally and spatially compatible runs remain distinct.
- Simulator device IDs are run-scoped.

## Catalog and parameters

Every catalog parameter declares type, default, minimum, maximum, unit, and description. Unknown parameters are rejected. The normalized effective set is stored on the run.

| Parameter | Default | Bounds | Unit | Scenarios |
|---|---:|---:|---|---|
| `devices` | 25 | 4–500 | devices | all |
| `seed` | 42 | 0–2147483647 | integer | all |
| `packet_loss_fraction` | 0.25 | 0–0.95 | fraction | degraded |
| `network_jitter_ms` | 900 | 0–5000 | milliseconds | degraded |
| `trigger_propagation_interval_ms` | 70 | 0–1000 | milliseconds | same-cell, distributed, degraded |

No center-point control is exposed. Degraded defaults preserve the prior deterministic seed-42, 25% loss, 900 ms maximum delivery jitter, and 70 ms propagation behavior. Network jitter delays delivery and never falsifies observation timestamps.

| Scenario | Injection | Expected |
|---|---|---|
| isolated | one trigger | `NO_CONFIRMATION`; device diversity fails |
| same-cell | multiple devices at one point | `NO_CONFIRMATION`; spatial diversity fails |
| distributed | coherent devices across cells | `CONFIRMATION` |
| degraded | distributed evidence with deterministic loss/jitter | `CONDITIONAL` |

## Stage vocabulary

The implemented vocabulary is:

`RUN_REQUESTED`, `PREFLIGHT_COMPLETED`, `FLEET_PREPARED`, `HEARTBEAT_GENERATED`, `INGRESS_ACCEPTED`, `SCHEMA_VALIDATED`, `REPLAY_GATE_EVALUATED`, `MOTION_GATE_EVALUATED`, `H3_CANONICALIZED`, `EVIDENCE_STORED`, `CORRELATION_STARTED`, `RECENCY_GATE_EVALUATED`, `DEVICE_DIVERSITY_GATE_EVALUATED`, `SPATIAL_DIVERSITY_GATE_EVALUATED`, `COHERENCE_GATE_EVALUATED`, `EVENT_TRANSITIONED`, `FOOTPRINT_COMPUTED`, `FRONTIER_COMPUTED`, `TARGETING_EVALUATED`, `ALERT_RECORDED`, `ALERT_ACKNOWLEDGED`, `RUN_EVALUATED`, `RUN_COMPLETED`, `RUN_FAILED`.

Stages are emitted only after their operation occurs. A negative run has failed gate stages but no event, footprint, frontier, targeting, or alert stage.
