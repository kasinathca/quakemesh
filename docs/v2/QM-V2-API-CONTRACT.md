# QuakeMesh V2 local API contract

The local control plane uses JSON schema version `2.0`. Timestamps are UTC epoch milliseconds. Every non-stream response has a request ID.

## Envelopes

Successful response:

```json
{"schema_version":"2.0","request_id":"uuid","data":{}}
```

Error response:

```json
{
  "schema_version": "2.0",
  "error": {
    "code": "SCENARIO_ALREADY_RUNNING",
    "message": "A scenario run is already active.",
    "request_id": "uuid",
    "details": {}
  }
}
```

Errors never contain stack traces, credentials, tokens, or raw coordinates. Stable local codes include `REQUEST_VALIDATION_FAILED`, `TELEMETRY_VALIDATION_FAILED`, `INVALID_SCENARIO_PARAMETERS`, `SCENARIO_ALREADY_RUNNING`, `SCENARIO_RUN_NOT_ACTIVE`, `SCENARIO_RUN_NOT_FOUND`, `SCENARIO_RESET_BLOCKED`, `EVENT_NOT_FOUND`, `ALERT_NOT_FOUND`, `ALERT_DEVICE_MISMATCH`, `INVALID_STREAM_CURSOR`, `LOCAL_CONTROL_FORBIDDEN`, and `INTERNAL_ERROR`.

## Read endpoints

| Endpoint | Data |
|---|---|
| `GET /health` | status, LOCAL mode, application version, safe counts |
| `GET /v1/config` | detector values and scenario capability policy |
| `GET /v1/devices` | safe device ID, transport, coarse H3 cell, last seen/sequence, provenance |
| `GET /v1/events` | authoritative events, provenance, footprint/frontier polygons |
| `GET /v1/events/{event_id}` | one event or `EVENT_NOT_FOUND` |
| `GET /v1/alerts` | target/delivery/ACK timestamps and provenance, never FCM tokens |
| `GET /v1/scenarios` | catalog, supported parameters, defaults, bounds, and units |
| `GET /v1/scenario-runs` | run summaries |
| `GET /v1/scenario-runs/{run_id}` | run metadata and ordered stages |
| `GET /v1/session` | LOCAL mode and active run; no fabricated AWS expiry |

List endpoints accept a bounded `limit` where applicable.

## Ingress

- `POST /v1/devices/heartbeat`
- `POST /v1/evidence/trigger`

Controlled-run ingress carries `X-QuakeMesh-Run-Id`. Omitting it means physical provenance. A run header must reference a RUNNING run. Observation payload schemas remain version `1.0`; the V2 API envelope is independent of device observation schema version.

## Local demo controls

Controls are loopback-only.

`POST /v1/demo/scenario-runs`:

```json
{
  "scenario": "distributed",
  "source": "dashboard",
  "parameters": {
    "devices": 25,
    "seed": 42,
    "trigger_propagation_interval_ms": 70
  }
}
```

The response is HTTP 202. `devices` and `seed` are also accepted as compatibility top-level fields, but conflicting duplicate values are rejected. Unknown or out-of-range parameters are rejected. Atomic server policy permits one QUEUED/RUNNING controlled run.

- `POST /v1/demo/reset` transactionally removes scenario-only runs, stages, evidence, events, alerts, and virtual devices. It refuses an active run and preserves physical records/configuration.
- `POST /v1/demo/scenario-runs/{run_id}/export` writes `artifacts/session_exports/local/<run_id>/run-evidence.json`.
- `POST /v1/alerts/{alert_id}/ack` accepts `{acknowledgement_source, device_id?}`. Repetition succeeds without another transition.

Cancellation is intentionally absent: the current simulator cannot guarantee safe interruption.

## Telemetry stream

`GET /v1/telemetry/stream` is Server-Sent Events. Each event has:

```json
{
  "schema_version": "2.0",
  "event_type": "scenario.stage",
  "sequence": 123,
  "emitted_at_ms": 1780000000000,
  "data": {}
}
```

SSE `id` equals the monotonic stream sequence. Browsers reconnect with `Last-Event-ID`; clients may also use `?after=<sequence>`. REST run/event/alert endpoints are the recovery snapshot after disconnect or a suspected gap.
