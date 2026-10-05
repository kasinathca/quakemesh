# Scenario engine specification

## Model

A catalog entry defines `scenario_id`, name, purpose, expected outcome, default parameters, and supported transports. A run records `run_id`, catalog/version, source (`cli`, `dashboard`, `android`, `test`), mode, seed, parameters, timestamps, status, expected outcome, observed outcome, event IDs, and error.

Run IDs use `QMR-<UTC compact timestamp>-<random suffix>`. Simulator ground truth stays in trace/run metadata and is rejected by observation schemas.

## Required behavior

| Scenario | Injection | Expected |
|---|---|---|
| isolated | one trigger | no confirmation; device gate fails |
| same-cell | multiple unique devices at one location | no confirmation; spatial gate fails |
| distributed | coherent devices spanning required cells | confirmation |
| degraded | distributed input with deterministic loss/jitter | conditional, based on surviving evidence |

## Stage vocabulary

`RUN_REQUESTED`, `FLEET_PREPARED`, `OBSERVATION_INJECTED`, `INGRESS_ACCEPTED`, `SCHEMA_VALIDATED`, `MOTION_GATE_EVALUATED`, `EVIDENCE_STORED`, `CORRELATION_EVALUATED`, `EVENT_TRANSITIONED`, `TARGETING_EVALUATED`, `ALERT_DISPATCHED`, `ALERT_ACKNOWLEDGED`, `RUN_COMPLETED`, `RUN_FAILED`.

Every stage has ID, run ID, timestamp, component, severity, message, and structured data. Stages may be absent when a path does not execute; clients must not synthesize them.
