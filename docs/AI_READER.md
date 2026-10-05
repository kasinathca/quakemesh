# QuakeMesh — AI / Maintainer Reader

Use this as the concise source of truth before modifying code.

## Purpose

QuakeMesh is a cloud-computing academic prototype that studies whether geographically diverse smartphone-derived motion triggers can be correlated in a serverless cloud backend and used to disseminate a targeted warning. It is **not** a certified earthquake early-warning system.

## Locked exclusions

Do not add or claim:

- earthquake magnitude estimation;
- epicentre/hypocentre estimation;
- official or public-safety authority;
- user accounts;
- Byzantine consensus, device reputation or PKI beyond the existing AWS IoT X.509 identity model in V1. Those belong to future work.

## Locked implementation decisions

- One Windows PC can run many Python virtual phones plus 1–2 Android emulators.
- A physical Android phone uses the same Android app source.
- Python simulators may use local HTTP or AWS IoT Core MQTT/mTLS.
- Primary AWS ingress is AWS IoT Core → IoT Rule → Lambda.
- The controlled HTTPS write fallback is API Gateway + API key and is for demonstration only.
- DynamoDB is authoritative cloud state.
- H3 is the spatial identity; raw coordinates are not persisted by QuakeMesh application tables.
- Event confirmation requires distinct devices **and** distinct geographic H3 cells within a temporal window and coherent spatial cluster.
- Correlator concurrency is deliberately serialized to 1 in V1 and event writes are still conditional/versioned.
- Android alerts use SNS/FCM when configured. Python clients receive MQTT alerts.
- S3 is only for experiment/archive artifacts, not authoritative event state.
- CloudWatch handles metrics/alarms/logs.
- No VPC, NAT Gateway, EC2, ECS, EKS, RDS or always-on server in V1.

## Important configuration

Defaults in `src/quakemesh_core/config.py` are **experimental engineering thresholds**, not seismological constants:

- device H3 resolution: 9
- correlation H3 resolution: 7
- evidence window: 8 s
- minimum devices: 4
- minimum distinct correlation cells: 3
- maximum cluster grid distance: 6
- warning frontier ring: k=1
- event merge window: 20 s
- resolve inactivity: 30 s

Any report or presentation must describe these as configurable prototype parameters.

## Code ownership

`src/quakemesh_core/` contains pure/shared decision logic. Do not fork the decision algorithm inside AWS or local runtime.

`local_runtime/` supplies a dependency-realistic single-PC runtime with SQLite.

`simulator/` supplies deterministic virtual phones. Synthetic scenario truth must remain in trace metadata and must never be sent to the detector.

`aws/lambdas/` adapts the same domain semantics to DynamoDB/IoT/SNS.

`aws/infrastructure/` is the CDK deployment.

`android/` is the physical/emulated phone client. It has no “confirm earthquake” button.

`dashboard/` visualizes API results and H3-derived polygons.
