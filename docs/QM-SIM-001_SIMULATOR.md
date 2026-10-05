# QM-SIM-001 — Virtual Phone Simulator

## Purpose

Generate reproducible multi-device workloads from one PC without pretending that synthetic motion is real seismological validation.

## Fleet model

`Fleet.around()` creates unique device IDs and deterministic geographic placement around a configurable center. Each virtual phone owns a monotonic sequence counter.

## Scenarios

- `isolated`: one trigger; expected negative.
- `same-cell`: multiple virtual phones temporarily share one coordinate; expected negative because cell diversity is absent.
- `distributed`: multiple geographically separated phones trigger; expected positive under default configuration.
- `degraded`: larger distributed set with deterministic 25% packet-loss decision and up to 900 ms jitter.

## Truth isolation

Each experiment trace may contain:

```json
"simulator_truth": {"scenario":"distributed_positive","injected":true}
```

That object is generated only by the experiment harness. It is **not** part of trigger/heartbeat payloads. Detector messages contain only device, sequence, timestamp, coordinates and motion features.

## Transports

### HTTP

Used for local runtime and optionally the controlled AWS API-key fallback.

### MQTT/mTLS

`AwsIotTransport` keeps one long-lived AWS IoT SDK connection per virtual phone. Certificates are loaded from per-Thing directories created by the provisioning script.

## Reproducibility

The CLI exposes `--seed`. Trace records are written under `artifacts/traces/`. Run metadata should include the exact command, Git commit, configuration and cloud region before results are used in a report.

## Timing model

`observed_at_ms` models when synthetic motion reaches a virtual device. Default runs shift the first observation into the recent past so no device is future-dated during concurrent dispatch. `network_delay_ms` is hidden simulator truth and delays transmission; it is not added to the sensor observation timestamp. This separation is required for meaningful temporal-correlation experiments.
