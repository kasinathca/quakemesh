# QM-SEC-001 — Security and Privacy

## 1. Trust model

### Primary simulator/AWS path

Each Python virtual phone is provisioned as an AWS IoT Thing with an X.509 certificate/private key. The policy scopes connect/publish/subscribe/receive to that Thing name. TLS/mTLS is terminated by AWS IoT Core.

Private keys live only under `artifacts/iot-devices/` and are gitignored.

### HTTPS fallback

API Gateway requires an API key for heartbeat and trigger POST methods. This removes anonymous internet writes, but an API key embedded in an Android APK is **not strong device identity** and can be extracted. Therefore this path is explicitly a controlled academic-demo fallback, not a production authentication design.

A production redesign should use device-bound credentials/attestation or an appropriate authenticated mobile identity service.

## 2. Replay/idempotency

- device state accepts only `seq > last_seq`;
- evidence ID is `<device_id>:<seq>` and written conditionally;
- event update uses `version` conditional write;
- alert delivery record is conditionally created by event+device.

## 3. Location minimization

Raw GPS coordinates are needed at ingress to compute H3, but are not columns/attributes in application device/evidence/event persistence. Device state stores H3 identifiers. Logs must not deliberately log incoming full request bodies.

This is data minimization, not anonymity: H3 cells still encode approximate geographic area and should be treated as location-related data.

## 4. FCM/SNS credentials

`google-services.json`, Android `local.properties`, Firebase service-account material, runtime API key export, certificates and private keys are gitignored. SNS platform application configuration is account-specific and is not embedded in this repository.

## 5. IAM principle

Lambdas receive table-specific grants and explicit IoT/SNS permissions needed by their role. No Lambda is placed in a VPC. The dispatcher may call `iot:DescribeEndpoint` and publish only to the QuakeMesh alert-topic pattern.

## 6. Secret scan

Run `scripts/check_secrets.py` before every push/release. It detects common AWS access-key/private-key patterns and fails if generated credential files are present in the repository tree.

## Timestamp and trigger hardening

Both local and AWS ingest reject non-finite numeric observations and observations outside the configured device/cloud clock-skew window. A trigger must also satisfy the defensive RMS/peak motion gate before it becomes persisted evidence. These checks limit malformed/replayed client input; they are not seismological validation.
