# QM-DATA-001 — Data Model

## 1. Data-retention principle

Raw latitude/longitude is accepted only to perform immediate H3 canonicalization. QuakeMesh application persistence stores H3 cells instead of the submitted coordinates.

## 2. DeviceState

AWS partition key: `device_id`.

Important attributes:

- `last_seq` — monotonic replay guard;
- `last_seen_ms`;
- `h3_cell`;
- `correlation_cell`;
- `transport`;
- optional `fcm_endpoint_arn`.

GSI: `cell-lastseen-index` with partition key `correlation_cell` and sort key `last_seen_ms`; used for target-device lookup.

## 3. Evidence

AWS key:

- PK `bucket = B#<observed_at_ms // 10000>`;
- SK `evidence_id = <device_id>:<seq>`.

Attributes include device ID, sequence, timestamps, H3 cells, motion RMS/peak and transport. `ttl` removes experiment evidence after the configured retention period.

Ten-second bucket partitioning is adequate for the academic prototype but should be replaced/sharded before very large deployments to avoid hot partitions.

## 4. Events

PK: `event_id`.

Attributes:

- `status` (`CONFIRMED` or `RESOLVED` in V1 persistence);
- creation/update/first/last timestamps;
- `version`;
- `device_ids`;
- `detection_footprint`;
- `warning_frontier`;
- `evidence_ids`.

GSI `status-updated-index` supports stale-event/operational lookup. The V1 correlator deliberately uses a strongly consistent base-table scan over the small active-event working set to avoid immediate GSI propagation lag; a scale-out design must replace that scan with explicit shard ownership.

## 5. AlertDelivery

PK: `alert_id = <event_id>:<device_id>`.

This key intentionally ignores event version: when an event footprint expands, newly targeted devices can receive their first alert without repeatedly notifying devices already warned for that same event.

Attributes include event/version/device/time/status/detail.

## 6. Local SQLite parity

Local runtime tables mirror the logical cloud entities: `devices`, `evidence`, `events`, `alerts`. The SQLite evidence/device schemas also omit raw latitude and longitude.
