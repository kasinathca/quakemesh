# Test plan

| Layer | Required checks | Current evidence |
|---|---|---|
| Domain | thresholds, recency, spatial components, replay, merge, frontier | PASS in 101-test suite; real H3 executed |
| Schemas | closed contracts and parity | PASS; 7 schemas plus privacy checks |
| Local persistence/service | lifecycle, concurrency, ACK, runs/stages/reset | PASS in Python and Playwright flows |
| Simulator/evaluation | deterministic scenarios, loss/jitter, truth separation, metrics | PASS; 48/48 seeded trials, real H3, artifacts tracked |
| PowerShell | nested-argument/process-launch regression | PASS |
| Dashboard | component/state/accessibility/build/E2E/evaluation exports | PASS; 7 unit and 2 browser tests |
| Android | parsing, state, API, notification, navigation, dedupe, build/lint | PASS for 12 JVM tests/build/lint; device limitations documented |
| CDK/AWS source | mappings, policies, ownership, cleanup, diagnostics | PASS in source/regression tests and prior synth |
| Live AWS | ingestion, correlation, delivery, stop, zero-resource report | VERIFIED for `qm-20261019-112257-b77a`; automatic expiry failed to complete on time |
| Live FCM | controlled receipt/open on physical device | VERIFIED for labeled controlled test; authoritative ACK remains unverified |

Local E2E must reset state, run isolated and same-cell with no confirmation, run distributed with confirmation, and verify footprint/frontier/alerts/stages in a machine-readable report. Skipped prerequisites are reported as `SKIPPED`, never `PASSED`.
