# QM-ARCH-001 — Architecture

## 1. Local vertical slice

```text
Python virtual phones ──HTTP──► FastAPI local runtime
                                   │
                                   ├─ H3 canonicalization
                                   ├─ shared correlation engine
                                   ├─ SQLite state/evidence/events/alerts
                                   └─ REST + WebSocket snapshot
                                            │
                                            ▼
                                       Dashboard
```

This path exists so the demonstration is not dependent on AWS availability during a review. It uses the same domain configuration and correlation code as the cloud adapter.

## 2. AWS vertical slice

```text
Python virtual phones ─MQTT/mTLS─┐
                                 ├─► AWS IoT Core
                                 │       │ IoT Rules
                                 │       ▼
                                 │   Ingress Lambda
Android ─HTTPS/API key───────────┴───────┤
                                         ├─► DeviceState DynamoDB
                                         └─► Evidence DynamoDB (TTL + stream)
                                                        │
                                                        ▼
                                                Correlator Lambda
                                                        │
                                                        ▼
                                                Events DynamoDB
                                                     stream
                                                        │
                                                        ▼
                                                Dispatcher Lambda
                                                  │            │
                                                  ▼            ▼
                                             IoT MQTT       SNS / FCM
                                             simulators       Android

EventBridge schedule ─► Resolver Lambda ─► Events DynamoDB
REST API GET ─► API Lambda ─► Events / AlertDelivery
CloudWatch ◄─ Lambda logs, X-Ray tracing and error alarms
S3 ◄─ experiment/archive uploads only
```

## 3. Shared-core rule

The detector is implemented in `src/quakemesh_core/`. Adapters may validate transport identity, persist state and call the core, but they must not implement independent threshold logic.

## 4. Event lifecycle

1. `trigger` accepted after schema and sequence validation.
2. raw coordinates exist only transiently in the inbound payload/application memory.
3. coordinates are converted to H3 device and correlation cells.
4. evidence is stored with short TTL.
5. correlation evaluates recent evidence.
6. when distinct-device, distinct-cell, temporal and coherence rules pass, event becomes `CONFIRMED`.
7. compatible new evidence expands the active event and increments `version`.
8. dispatcher evaluates the new footprint/frontier and alerts devices not already alerted for that event.
9. resolver marks inactive events `RESOLVED`.

## 5. Correctness-first concurrency

The V1 correlator Lambda has reserved concurrency `1`, uses strongly consistent base-table reads for the small active-event working set, and writes events with a `version` plus conditional writes. This avoids depending on immediate GSI propagation for correctness during an academic-scale demonstration. This is intentionally not presented as the final scale-out design. A larger deployment should partition correlation ownership spatially/temporally instead of simply increasing concurrency.

## 6. Failure behavior

- duplicate/replayed sequence: ignored;
- duplicate evidence ID: conditional write rejects it;
- malformed schema: rejected before persistence;
- H3 unavailable: runtime fails loudly rather than substituting a fake grid;
- isolated trigger: evidence may exist but no event confirmation;
- same-cell burst: insufficient spatial diversity;
- unrelated distant evidence: spatial components are evaluated separately;
- Lambda delivery failure: alert record is marked `FAILED` and stream retry can surface the error;
- no SNS platform application: MQTT delivery still functions and FCM path remains disabled until configured.
