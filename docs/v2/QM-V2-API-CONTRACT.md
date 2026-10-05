# API contract

All JSON uses version `2.0`, UTC epoch milliseconds, stable error codes, and `application/json`. Local and AWS modes expose equivalent shapes.

## Reads

- `GET /health` — mode, service status, safe build/schema metadata.
- `GET /v1/config` — non-secret detection thresholds and capabilities.
- `GET /v1/events`, `/v1/events/{id}` — authoritative event views.
- `GET /v1/devices` — coarse cell, last seen, transport, safe status.
- `GET /v1/alerts` — delivery/acknowledgement state without tokens.
- `GET /v1/scenarios` — catalog.
- `GET /v1/scenario-runs`, `/v1/scenario-runs/{id}` — run and stage state.
- `GET /v1/session` — local or AWS lifecycle state without credentials.

## Controls

- `POST /v1/demo/scenario-runs` with `{scenario, devices, seed, parameters}` returns `202` and a run.
- `POST /v1/demo/reset` clears experiment data only.
- `POST /v1/alerts/{id}/ack` is idempotent and records acknowledgement time/source.

Demo controls require a local-only trust boundary or session-scoped credential, rate limit, validation, and audit stage. They are disabled by default on an unconfigured public deployment.

Errors use `{schema_version, error:{code,message,request_id,details?}}`; details never contain secrets. WebSocket/SSE messages wrap `{schema_version,type,sequence,emitted_at_ms,data}` and clients recover through a snapshot endpoint after gaps.
