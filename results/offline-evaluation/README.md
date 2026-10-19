# Offline synthetic evaluation snapshot

This directory contains the sanitized, report-ready output from the deterministic QuakeMesh software evaluation generated on 2026-10-19 with 12 trials per scenario and base seed `20261019`.

The results are **controlled synthetic simulation results**, not real-world earthquake-detection accuracy. Injected truth is retained only by the evaluator and is never provided to the detector. Each trial uses a fresh SQLite database, the production `QuakeMeshService`, unchanged detection thresholds, and the production `H3GeoIndex` backed by real `h3-py`.

Contents:

- `summary.json`: aggregate confusion matrix, metrics, confidence intervals, latency, transport delivery, configuration, and robustness groups.
- `trials.csv`: all 48 independent trial records and reproducible seeds.
- `robustness.csv`: grouped network-condition results.
- `REPORT.md`: human-readable methodology and results.
- `confusion-matrix.svg` and `robustness-by-network.svg`: report figures.

Regenerate the complete ignored artifact set and dashboard data from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --output artifacts\evaluation\latest --trials-per-scenario 12 --base-seed 20261019 --publish-dashboard
```

After regeneration, compare the machine-readable values before intentionally refreshing this tracked snapshot. The `generated_at` timestamp will differ; deterministic seeds, trial inputs, predictions, and aggregate measurements must remain reproducible.
