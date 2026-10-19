# QuakeMesh offline synthetic evaluation report

> **Simulation result only.** These measurements evaluate deterministic synthetic scenarios against the QuakeMesh software detector. They are not estimates of real-world earthquake-detection accuracy.

Generated: 2026-10-19T14:02:03.126508+00:00

Trials: 48 completed / 48 requested; 0 failed.

## Event-level confusion matrix

| | Predicted positive | Predicted negative |
|---|---:|---:|
| Injected positive | TP 24 | FN 0 |
| Injected negative | FP 0 | TN 24 |

| Metric | Value |
|---|---:|
| Accuracy | 1.0000 |
| Precision | 1.0000 |
| Recall | 1.0000 |
| Specificity | 1.0000 |
| F1 | 1.0000 |
| False-positive rate | 0.0000 |
| False-negative rate | 0.0000 |

All ratio confidence intervals in `summary.json` are two-sided 95% Wilson intervals. Undefined zero-denominator metrics are serialized as JSON `null`, never coerced to a perfect or zero score.

## Method

Each trial uses a fresh SQLite database, `QuakeMeshService`, the unchanged `DetectionConfig`, and the production `H3GeoIndex` backed by h3-py. Seeds deterministically control device count, geographic center, grid spacing, trigger motion values, loss, jitter, and arrival order. Isolated and same-cell trials are negative injected truth; distributed and degraded trials are positive injected truth. Truth is retained only by this evaluator and is never included in heartbeat or trigger payloads.

Confirmation latency is logical simulated elapsed time from the first injected trigger observation to the delivery that first yields a confirmed event. Alert-target latency ends at the first local authoritative target record. Mean latency 95% intervals use a deterministic percentile bootstrap. Transport delivery is distinct from targeting. Actual notification receipt is unobserved offline and is never inferred from target creation.

Confirmation latency: mean 513.7500 ms; median 469.5000 ms.

Alert-target latency: mean 513.7500 ms; median 469.5000 ms.

See `trials.csv`, `trials.json`, `summary.json`, `robustness.csv`, and the SVG figures for reproducible data.
