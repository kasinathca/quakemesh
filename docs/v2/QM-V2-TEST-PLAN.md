# Test plan

| Layer | Required checks | Current evidence |
|---|---|---|
| Domain | thresholds, recency, spatial components, replay, merge, frontier | PASS in final 111-test repository suite; real H3 executed |
| Schemas | closed contracts and parity | PASS; 7 schemas plus privacy checks |
| Local persistence/service | lifecycle, concurrency, ACK, runs/stages/reset | PASS in Python and Playwright flows |
| Simulator/evaluation | deterministic scenarios, loss/jitter, truth separation, metrics | PASS; 48/48 seeded trials, real H3, artifacts tracked |
| PowerShell | nested-argument/process-launch regression | PASS |
| Dashboard | component/state/accessibility/build/E2E/evaluation exports | PASS; 7 unit and 3 browser tests |
| Android | parsing, state, API, notification, full-screen warning, attention controls, navigation, dedupe, build/lint | PASS for JVM tests/build/lint and named physical-handset final flow |
| CDK/AWS source | mappings, policies, ownership, cleanup, diagnostics | PASS in source/regression tests and prior synth |
| Live AWS | interactive scenarios, ingestion, correlation, delivery, stop, zero-resource report | VERIFIED for final `qm-20261023-190030-20bc`; automatic expiry remains outside the final scope |
| Live FCM | USB-disconnected authoritative receipt/open/audio-stop/ACK | VERIFIED on named handset/session; unlocked heads-up and locked full-screen behavior distinguished |

Local E2E must reset state, run isolated and same-cell with no confirmation, run distributed with confirmation, and verify footprint/frontier/alerts/stages in a machine-readable report. Skipped prerequisites are reported as `SKIPPED`, never `PASSED`.
