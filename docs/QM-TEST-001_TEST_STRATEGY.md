# QM-TEST-001 — Test Strategy

## Test layers

### Pure domain

Runs without AWS and, for most cases, without the external H3 binary by injecting a deterministic geo adapter. Tests cover:

- positive corroboration;
- isolated-device rejection;
- same-cell rejection;
- duplicate-device suppression;
- stale evidence rejection;
- separation of distant components;
- frontier derivation;
- event creation/merge/versioning;
- deterministic event key;
- schema bounds;
- motion gate.

### Local persistence/service

Tests SQLite end-to-end event creation, replay rejection and absence of raw coordinate columns.

### Simulator

Tests unique IDs, deterministic fault injection and ground-truth isolation from transmitted messages.

### Repository contract/static

Checks versioned schemas, infrastructure security invariants, absence of forbidden V1 infrastructure, Python compilation and dashboard/XML parsing.

### Real H3 integration

A separate test imports `h3` and validates production adapter operations. It is skipped only when the external `h3` dependency is unavailable. On the user PC after `scripts/setup.ps1`, it must run rather than skip.

### AWS integration

After deployment, execute the scenario matrix against real IoT Core and inspect DynamoDB/CloudWatch/alert records. Local unit tests do not count as proof that an AWS account was successfully deployed.

### Android integration

A successful Gradle build, emulator run, physical-phone run, FCM receipt and permission behavior must be validated on the user’s Android development machine/device.

## Release gates

1. all Python files byte-compile;
2. pytest has no failures;
3. real-H3 test does not skip in the configured development environment;
4. Ruff critical checks pass;
5. JSON/XML/JS structural checks pass;
6. secret scan passes;
7. no generated credential artifacts are inside the release repository;
8. AWS deployment and Android build are reported separately as environment-dependent verification, never silently assumed.
