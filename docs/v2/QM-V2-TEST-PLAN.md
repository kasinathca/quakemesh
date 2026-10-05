# Test plan

| Layer | Required checks | Current evidence |
|---|---|---|
| Domain | thresholds, recency, spatial components, replay, merge, frontier | 41-test baseline includes core cases |
| Schemas | closed contracts and parity | V1 trigger/heartbeat/alert only |
| Local persistence/service | lifecycle, concurrency, ACK, runs/stages/reset | event path tested; V2 additions pending |
| Simulator | deterministic scenarios, loss/jitter, truth separation | V1 tested |
| PowerShell | AST parse and nested-argument regression | pending |
| Dashboard | component/state/accessibility/build/E2E | pending |
| Android | parsing, state, API, notification, Compose UI/build | pending |
| CDK | synth, policies, ownership tags, deletion, TTL target | pending |
| Live AWS | start, scenario, delivery, stop, zero-resource report | blocked by authenticated account and explicit start |
| Live FCM | receipt/open/ACK on emulator or device | blocked by Firebase/device setup |

Local E2E must reset state, run isolated and same-cell with no confirmation, run distributed with confirmation, and verify footprint/frontier/alerts/stages in a machine-readable report. Skipped prerequisites are reported as `SKIPPED`, never `PASSED`.
