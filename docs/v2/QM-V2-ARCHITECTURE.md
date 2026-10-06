# QuakeMesh V2 architecture

## Domain boundaries

- **Observation:** device-reported heartbeat or motion features.
- **Evidence:** a validated, motion-gated, H3-canonicalized trigger.
- **Evaluation truth:** simulator-only labels and expected results; never accepted by ingestion.
- **Event:** authoritative server-side corroboration state.
- **Alert delivery:** target and transport outcome, separate from event truth.
- **Scenario run:** controlled experiment metadata and stage telemetry. Scenario events retain the run ID.
- **Cloud session:** owned infrastructure metadata and expiry, separate from application state.

## Local

```mermaid
flowchart LR
  CLI[PowerShell CLI / Dashboard / future Android] --> C[ScenarioControlService]
  C --> F[Virtual-phone fleet]
  P[Physical phone sensors] --> API[FastAPI]
  F --> API
  API --> D[Shared domain engine]
  D --> DB[(SQLite)]
  DB --> API
  API -->|V2 REST snapshots + SSE stages| UI[React dashboard]
  API --> A[Android alert/ACK]
```

## AWS

```mermaid
flowchart LR
  SIM[Virtual phones] -->|mTLS MQTT| IOT[AWS IoT Core]
  PHONE[Android HTTPS] --> APIGW[API Gateway]
  IOT --> ING[Ingress Lambda]
  APIGW --> API[API Lambda]
  ING --> DD[(DynamoDB)]
  API --> DD
  DD --> CORR[Correlator Lambda]
  CORR --> EVT[(Events)]
  EVT --> DISP[Dispatcher Lambda]
  DISP -->|MQTT| SIM
  DISP -->|SNS/FCM optional| PHONE
  EXP[Session expiry] --> CLEAN[Restricted cleanup]
  CLEAN --> STACK[Exact session stack deletion]
```

## Scenario and alert sequences

```mermaid
sequenceDiagram
  participant U as Control client
  participant R as Run coordinator
  participant F as Fleet
  participant E as Engine
  participant T as Telemetry store
  U->>R: start scenario
  R->>T: run requested
  R->>F: inject deterministic observations
  F->>E: heartbeat/trigger
  E->>T: validation and gate stages
  E-->>R: authoritative result
  R->>T: complete/fail run
```

```mermaid
sequenceDiagram
  participant E as Confirmed event
  participant D as Dispatcher
  participant P as Phone/simulator
  participant A as Alert store
  E->>D: event version
  D->>A: idempotent delivery claim
  D->>P: experimental warning
  P->>A: acknowledgement
```

Local and AWS adapters must implement the same public schemas; storage and transport details may differ.

Local correlation is partitioned by `(provenance_type, scenario_run_id)`. Physical records use `physical` plus a null run ID; every controlled run uses `scenario` plus its run ID. The same partition applies to active-event merging and alert targeting. SQLite `BEGIN IMMEDIATE` makes the one-active-run policy atomic.

The current local runner has no safe interruption primitive, so the public contract intentionally omits cancellation rather than presenting a non-functional control.
