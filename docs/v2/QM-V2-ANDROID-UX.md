# Android UX specification and implementation status

## Implemented foundation (2026-10-07)

The current Android V2 client has a restrained, scrollable monitoring interface with explicit environment/API, device identity, sensor, location, heartbeat, local-motion, corroborated-alert, and acknowledgement states. It deliberately separates **LOCAL MOTION OBSERVED** from **CLOUD-CORROBORATED EVENT** and states that QuakeMesh is an experimental research system rather than an official warning service.

Networking parses V2 success/error envelopes and preserves HTTP status, stable server code, message, request ID, details, timeout, connection, configuration, and invalid-response states. Heartbeat and trigger payloads remain schema `1.0`. Physical requests never add `X-QuakeMesh-Run-Id`. The ignored API key is sent only when configured, so local FastAPI works without one.

Debug emulator builds default to `http://10.0.2.2:8000`. Debug network policy permits cleartext only for `10.0.2.2`, localhost, and `127.0.0.1`; the main/release manifest remains cleartext-disabled.

The foreground service publishes monitoring, sensor availability, coarse location availability (not coordinates), recurring heartbeat result, and local motion state. Alert polling supports local FastAPI. FCM parsing uses `alert_id` as the primary deduplication identity, persists the latest alert, and retains a legacy event fallback only for older messages. ACK calls `POST /v1/alerts/{alert_id}/ack` with Android source and physical device identity; notification dismissal does not imply ACK.

Verified on the current Windows host: debug Kotlin/Java compilation, APK assembly, and Android lint. Unit-test task currently has no source tests. Emulator, physical-device sensors/location, actual local traffic, process recreation, TalkBack, and FCM delivery are not yet verified.

## Target evolution

Material 3 navigation destinations: Status, Monitoring, Alerts, Demo Lab, and About. The app must state “Experimental QuakeMesh event” and that confirmation reflects configured corroboration rules, not an official warning.

Status shows connectivity/configuration, monitoring permission/state, last heartbeat, and current session/mode when known. Monitoring preserves real accelerometer/location capture with explicit permission and foreground-service states. Alerts provide durable history, detail, delivery timestamp, event footprint summary, and idempotent acknowledgement. Demo Lab calls the same scenario contract as the dashboard and never routes synthetic control through the physical sensor path.

Layouts support compact portrait, handset landscape, and a larger window. Text scales, touch targets are at least 48dp, content descriptions and TalkBack order are deliberate, and status is not color-only. Missing Firebase/API configuration is an actionable configuration state, not a successful connection.

The implemented single-screen status surface is the first final-architecture checkpoint. The planned destination-level navigation, durable multi-alert history, footprint summary, responsive large-window layouts, and formal accessibility validation remain future increments rather than being falsely presented as complete.

Live FCM delivery remains `NOT VERIFIED` until a real Firebase project, permitted emulator/device, and receipt evidence exist.
