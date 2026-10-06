# QuakeMesh V2 dashboard UX

The dashboard is a static React 19 + strict TypeScript + Vite application. Dependencies are locked and bundled. Leaflet is imported from the bundle; OpenStreetMap tiles are optional and a tile failure leaves verified geometry available as text.

## Information architecture

Primary views are Overview, Live Map, Scenario Lab, Events, Devices, Alerts, Experiments, Infrastructure, and Session.

- Overview distinguishes unavailable data from zero and shows mode, health, active run, counts, confirmation, and last update.
- Scenario Lab renders catalog metadata, validated parameters, Start, Reset, Export, live status, expected/observed verdict, backend gates, full timeline, structured logs, and event-map evolution. Cancel is absent because cancellation is not safe.
- Events exposes provenance, devices, H3 cells, footprint/frontier, evidence, lifecycle, and related alerts.
- Devices exposes only safe coarse state and never tokens or raw coordinates.
- Alerts explains `TARGETED`, shows known timestamps/failures, and performs idempotent ACK.
- Experiments selects authoritative historical run records.
- Infrastructure shows local runtime/configuration only; Session shows `LOCAL` without an AWS countdown.

Structured log columns are timestamp, component, stage, severity, device, run, and message. Search, severity filter, autoscroll, copy, and JSON export operate on backend telemetry rows.

## Interaction and visual rules

The UI uses system typography, an 8 px spacing rhythm, restrained blue accent, dense tables, square-to-small-radius surfaces, semantic color plus status text, visible keyboard focus, and no marketing language, neon gradients, glass effects, emoji controls, or oversized cards.

The last verified snapshot remains visible during API/SSE loss with an explicit disconnected banner. A five-second REST refresh is the recovery baseline; stream events trigger targeted snapshot refresh rather than client-generated state.

Automated browser checks cover 1280×720, 1366×768, 1440×900, 1920×1080, and 390×844 with no page-level horizontal overflow. Evidence screenshots are written under `artifacts/e2e/`.
