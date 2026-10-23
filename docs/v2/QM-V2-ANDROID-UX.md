# Android UX specification and implementation status

## Implemented foundation (2026-10-07)

The current Android V2 client has a restrained, scrollable monitoring interface with explicit environment/API, device identity, sensor, location, heartbeat, local-motion, corroborated-alert, and acknowledgement states. It deliberately separates **LOCAL MOTION OBSERVED** from **CLOUD-CORROBORATED EVENT** and states that QuakeMesh is an experimental research system rather than an official warning service.

Networking parses V2 success/error envelopes and preserves HTTP status, stable server code, message, request ID, details, timeout, connection, configuration, and invalid-response states. Heartbeat and trigger payloads remain schema `1.0`. Physical requests never add `X-QuakeMesh-Run-Id`. The ignored API key is sent only when configured, so local FastAPI works without one.

Debug emulator builds default to `http://10.0.2.2:8000`. Debug network policy permits cleartext only for `10.0.2.2`, localhost, and `127.0.0.1`; the main/release manifest remains cleartext-disabled.

The foreground service publishes monitoring, sensor availability, coarse location availability (not coordinates), recurring heartbeat result, and local motion state. Alert polling supports local FastAPI. FCM parsing uses `alert_id` as the primary deduplication identity, persists the latest alert, and retains a legacy event fallback only for older messages. ACK calls `POST /v1/alerts/{alert_id}/ack` with Android source and physical device identity; notification dismissal does not imply ACK.

Verified on the current Windows host: 12 JVM tests, debug Kotlin/Java compilation, Firebase-enabled APK assembly, Android lint, installation and launch on Motorola device `ZD222HDG42`, physical heartbeat/H3 registration, physical motion evidence, notification navigation, foreground/background controlled previews, duplicate suppression, distinct warning/demo channels and bundled tones, and one uniquely labeled controlled FCM receipt. Controlled previews created no authoritative ACK records. Android 15 did not display an automatic heads-up overlay during the observed test, and QuakeMesh intentionally does not request full-screen intent. Process recreation, TalkBack, broad device coverage, and authoritative handset ACK remain unverified.

## Target evolution

Material 3 navigation destinations: Status, Monitoring, Alerts, Demo Lab, and About. The app must state “Experimental QuakeMesh event” and that confirmation reflects configured corroboration rules, not an official warning.

Status shows connectivity/configuration, monitoring permission/state, last heartbeat, and current session/mode when known. Monitoring preserves real accelerometer/location capture with explicit permission and foreground-service states. Alerts provide durable history, detail, delivery timestamp, event footprint summary, and idempotent acknowledgement. Demo Lab calls the same scenario contract as the dashboard and never routes synthetic control through the physical sensor path.

Layouts support compact portrait, handset landscape, and a larger window. Text scales, touch targets are at least 48dp, content descriptions and TalkBack order are deliberate, and status is not color-only. Missing Firebase/API configuration is an actionable configuration state, not a successful connection.

The implemented single-screen status surface is the first final-architecture checkpoint. The planned destination-level navigation, durable multi-alert history, footprint summary, responsive large-window layouts, and formal accessibility validation remain future increments rather than being falsely presented as complete.

Controlled live FCM receipt is verified for the named physical device and session documented in `QM-V2-AWS-PIPELINE-REPAIR.md`. This does not prove delivery reliability across devices or operating conditions, and the controlled message had no authoritative alert record, so ACK was correctly not generated.

## Controlled wireless telemetry extension — 2026-10-22

Data-only FCM messages of type `QUAKEMESH_CONTROLLED_TEST` are now parsed as non-authoritative controlled tests. The app reports `FCM_RECEIVED` when the Firebase callback runs, `NOTIFICATION_POSTED` after submitting the notification to Android, and `OPENED` when the tap destination starts. Receipts carry the stable test-message ID and physical device ID to the current session API. The visible title is exactly **CONTROLLED TEST — NOT AN EARTHQUAKE ALERT**. The controlled channel, stable delivery deduplication, notification permission, tap navigation, and no-full-screen policy remain intact.

JVM tests and Android lint/build validated the payload model and application code locally at that dated boundary.

## Final authoritative drill validation — 2026-10-24

The earlier limitations above are historical milestone statements. The final implementation now requests `USE_FULL_SCREEN_INTENT`, declares a locked-screen/screen-wake warning activity, and uses a foreground media-playback attention service for alarm-category tone, spoken warning, and vibration requests. The warning provides **ACKNOWLEDGE / DISMISS**, **STOP ALERT SOUND**, and **Dismiss** as distinct operations. Stable alert identity is retained across cloud dispatch, FCM parsing, presentation, receipts, acknowledgement, and duplicate suppression.

Session `qm-20261023-190030-20bc` verified a Motorola Edge 40 Neo physical handset as the current H3 reference and opted-in drill recipient. Virtual devices supplied all scenario evidence. With USB disconnected, an authoritative distributed scenario produced `FCM_RECEIVED`, `NOTIFICATION_POSTED`, `AUDIO_STARTED`, `OPENED`, and `AUDIO_STOPPED`, followed by `ACKNOWLEDGED` from Android. Locked/screen-off testing verified wake and full-screen presentation over the keyguard.

The user additionally confirmed that, while unlocked on the home screen and still disconnected from USB, Android displayed a heads-up notification with audible sound and spoken warning. Tapping it opened the full warning; **Stop Alert Sound** worked; then acknowledgement completed. This is the verified unlocked behavior and must not be restated as automatic full-screen takeover.

Remaining limitations are broad-device coverage, formal TalkBack/accessibility testing, and process-recreation testing. DND/silent-mode audible bypass and physical vibration strength are outside the final review scope.
