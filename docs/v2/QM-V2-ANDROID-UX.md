# Android UX specification

Material 3 navigation destinations: Status, Monitoring, Alerts, Demo Lab, and About. The app must state “Experimental QuakeMesh event” and that confirmation reflects configured corroboration rules, not an official warning.

Status shows connectivity/configuration, monitoring permission/state, last heartbeat, and current session/mode when known. Monitoring preserves real accelerometer/location capture with explicit permission and foreground-service states. Alerts provide durable history, detail, delivery timestamp, event footprint summary, and idempotent acknowledgement. Demo Lab calls the same scenario contract as the dashboard and never routes synthetic control through the physical sensor path.

Layouts support compact portrait, handset landscape, and a larger window. Text scales, touch targets are at least 48dp, content descriptions and TalkBack order are deliberate, and status is not color-only. Missing Firebase/API configuration is an actionable configuration state, not a successful connection.

Live FCM delivery remains `NOT VERIFIED` until a real Firebase project, permitted emulator/device, and receipt evidence exist.
