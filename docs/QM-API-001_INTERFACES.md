# QM-API-001 — Interfaces

## 1. Schema version

All device messages use `schema_version: "1.0"`. Unsupported versions are rejected.

## 2. Trigger

Topic for IoT clients:

`quakemesh/v1/devices/<device_id>/trigger`

HTTPS fallback:

`POST /v1/evidence/trigger` with `x-api-key`.

Example:

```json
{
  "schema_version": "1.0",
  "device_id": "QM-SIM-0001",
  "seq": 14,
  "observed_at_ms": 1788912000123,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "motion_rms": 1.21,
  "motion_peak": 2.47
}
```

Coordinates are transport inputs and are not retained in QuakeMesh application state after H3 canonicalization.

## 3. Heartbeat

IoT topic:

`quakemesh/v1/devices/<device_id>/heartbeat`

HTTPS fallback:

`POST /v1/devices/heartbeat` with `x-api-key`.

Optional Android `fcm_token` may be supplied to register/update an SNS platform endpoint when `QM_SNS_PLATFORM_APPLICATION_ARN` is configured.

## 4. Warning

IoT topic:

`quakemesh/v1/devices/<device_id>/alerts`

Representative payload:

```json
{
  "schema_version": "1.0",
  "type": "QUAKEMESH_WARNING",
  "event_id": "QM-...",
  "event_version": 2,
  "status": "CONFIRMED",
  "detected_at_ms": 1788912000456,
  "detection_footprint": ["..."],
  "warning_frontier": ["..."]
}
```

FCM uses the same event ID/version/status as data fields plus a human-readable high-priority notification.

## 5. Read API

- `GET /health`
- `GET /v1/events`
- `GET /v1/alerts`

The event view may include H3-derived polygon boundaries for dashboard visualization. These polygons are derived from cells and are not raw device positions.

## 6. IoT identity binding

IoT policy constrains each Thing to its own client ID and device topics. The IoT Rule also injects `topic()` into the Lambda event; ingress verifies the topic device ID equals the payload device ID.
