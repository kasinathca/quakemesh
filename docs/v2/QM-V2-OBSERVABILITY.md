# QuakeMesh V2 local observability

Scenario stages are persistent structured telemetry and the single source for dashboard logs and timelines. JavaScript does not manufacture progress.

Each stage stores stage ID, run ID, per-run sequence, occurrence timestamp, component, severity, status, message, structured data, and optional device/event/alert IDs and measured duration. Per-run sequence begins at one and increases without duplicates. The global stage ID is the SSE resume cursor.

The SSE stream at `/v1/telemetry/stream` emits schema `2.0`, event type, monotonic sequence, emission timestamp, and the complete stage. It sends keep-alives when idle, accepts `Last-Event-ID` or `after`, and exposes no raw coordinates, tokens, credentials, or simulator ground-truth labels.

REST remains authoritative for snapshot recovery. The dashboard refreshes at a five-second baseline, refreshes after stream events, retains its last good snapshot on failure, visibly marks disconnection, and recovers from REST when connectivity returns.

Local alert state uses `TARGETED`, `QUEUED`, `SENT`, `ACKNOWLEDGED`, and `FAILED`. Current simulator-only targeting records `TARGETED`; it does not claim receipt by a physical phone.
