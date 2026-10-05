# QM-EXP-001 — Experiment Plan

## Goal

Evaluate cloud-system behavior of QuakeMesh corroboration and alert dissemination under controlled synthetic workloads. The experiments test the software architecture, not earthquake-science accuracy.

## Fixed experiment metadata

Record for every run:

- experiment ID;
- Git commit hash;
- date/time/timezone;
- local or AWS transport;
- AWS region/account alias if applicable;
- simulator seed;
- device count;
- scenario;
- QuakeMesh threshold environment;
- trace file;
- event/alert records;
- CloudWatch timestamps for AWS runs.

## Scenario matrix

| ID | Scenario | Devices | Faults | Expected software outcome |
|---|---|---:|---|---|
| EXP-N01 | isolated | 25 fleet / 1 trigger | none | no confirmation |
| EXP-N02 | same-cell | 25 fleet / 6 triggers | no cell diversity | no confirmation |
| EXP-P01 | distributed | 25 / first 8 trigger | normal | confirmation expected |
| EXP-P02 | degraded | 25 / first 16 candidates | 25% deterministic loss + 0–900 ms jitter | confirmation if enough evidence survives |
| EXP-R01 | replay | manual/test | duplicate sequence | no evidence inflation |
| EXP-L01 | lifecycle | distributed then idle | > resolve threshold | confirmed → resolved |

## Metrics

Software metrics may include:

- ingest acceptance/rejection count;
- time from first accepted trigger to confirmed event state;
- number of distinct devices/cells at confirmation;
- event update count/version;
- dispatch count;
- first alert-delivery record delay;
- duplicate/replay rejection count;
- Lambda errors/throttles;
- DynamoDB consumed/request metrics if needed.

Do not label these measurements as earthquake warning lead time unless real seismic ground truth and appropriate scientific methodology exist.

## Repetition

For quantitative reporting, run each synthetic scenario using multiple seeds and report distribution (median, percentiles and failures) rather than selecting one favorable run.

## Evidence preservation

Simulator traces are stored locally under `artifacts/traces/`. Important run artifacts may be uploaded to the stack’s encrypted/versioned S3 archive. Do not upload private IoT keys or Firebase credentials.
