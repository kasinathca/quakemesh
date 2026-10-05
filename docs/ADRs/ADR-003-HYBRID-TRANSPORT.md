# ADR-003 — Hybrid transport

**Status:** accepted.

Device→cloud simulator traffic primarily uses MQTT/mTLS through AWS IoT Core. Cloud→Python warnings use MQTT. Android warnings use SNS→FCM. Android trigger/heartbeat uses a controlled API-key-gated HTTPS fallback in V1. The Android API key is not considered production-grade device authentication.
