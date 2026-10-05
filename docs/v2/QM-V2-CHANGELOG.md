# QuakeMesh V2 changelog

## 2026-10-05

- Recorded the forensic V1 baseline, verification gaps, dependency state, and strict-ephemeral conflicts.
- Established controlled V2 requirements, architecture, lifecycle, UX, scenario, observability, API, test, security, runbook, and traceability documents.
- Replaced brittle nested PowerShell positional argument construction with encoded parameter splatting and added a binding smoke test.
- Added local scenario-run persistence, structured stage telemetry, a loopback-only scenario control API, and run-aware HTTP simulator transport.
- Added stale-venv recovery, detect-first Windows setup, and AWS account/cost safety guides.
- Corrected stale-launcher probing so Windows native-process errors enter the environment rebuild path.
- Isolated controlled-run evidence from physical evidence and made degraded-run result extraction tolerate intentionally dropped simulator records.
- Added a responsive dashboard Scenario Lab that starts real local runs and renders authoritative gate and stage telemetry.
- Rebuilt the local environment with Python 3.12, verified all required scenarios over HTTP, completed a browser interaction/console check, and recorded machine-readable evidence.
