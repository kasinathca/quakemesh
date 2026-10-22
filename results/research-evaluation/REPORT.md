# QuakeMesh research evaluation

> **Scope:** event-level software simulation; not real-world earthquake accuracy. Labels are independent scenario semantics. No real earthquake handset ground truth is included.

Generated: 2026-10-22T15:25:24.383347+00:00

## Aggregate event-level results

320 completed trials (60 held out); 0 runner failures.

| | Predicted positive | Predicted negative |
|---|---:|---:|
| Ground-truth positive | TP 86 | FN 58 |
| Ground-truth negative | FP 25 | TN 151 |

Accuracy 0.740625; precision 0.7747747747747747; recall 0.5972222222222222; specificity 0.8579545454545454; F1 0.6745098039215687; F2 0.6259097525473072; balanced accuracy 0.7275883838383839; MCC 0.4757546425742966.

Each proportion includes a two-sided 95% Wilson interval in `summary.json`; undefined denominators remain JSON `null`. MCC is undefined when its denominator is zero. Ground-truth event times are matched one-to-one to the nearest unique detector event within 10000 ms. Unmatched truth is FN, unmatched confirmation is FP, and duplicate alerts do not create additional predictions. Failed executions are excluded and reported separately.

## Scenario results

| Scenario | n | TP | TN | FP | FN | F1 |
|---|---:|---:|---:|---:|---:|---:|
| coordinated-human-quorum | 16 | 0 | 4 | 12 | 0 | 0.0 |
| cycling | 16 | 0 | 16 | 0 | 0 | undefined |
| delayed-out-of-order | 16 | 4 | 0 | 0 | 12 | 0.4 |
| device-handling | 16 | 0 | 16 | 0 | 0 | undefined |
| duplicate-replay-stale | 16 | 0 | 15 | 1 | 0 | 0.0 |
| h3-boundary | 16 | 11 | 0 | 0 | 5 | 0.8148148148148148 |
| isolated-shaking | 16 | 0 | 16 | 0 | 0 | undefined |
| low-device-density | 16 | 13 | 0 | 0 | 3 | 0.896551724137931 |
| near-threshold-noise | 16 | 0 | 4 | 12 | 0 | 0.0 |
| network-loss-insufficient | 16 | 9 | 0 | 0 | 7 | 0.72 |
| orientation-and-noise | 16 | 12 | 0 | 0 | 4 | 0.8571428571428571 |
| partial-participation | 16 | 13 | 0 | 0 | 3 | 0.896551724137931 |
| phone-drop | 16 | 0 | 16 | 0 | 0 | undefined |
| repeated-single-device-vibration | 16 | 0 | 16 | 0 | 0 | undefined |
| same-cell-multi-device | 16 | 0 | 16 | 0 | 0 | undefined |
| strong-distributed | 16 | 13 | 0 | 0 | 3 | 0.896551724137931 |
| threshold-boundary | 16 | 7 | 0 | 0 | 9 | 0.6086956521739131 |
| uncorrelated-multi-location | 16 | 0 | 16 | 0 | 0 | undefined |
| walking | 16 | 0 | 16 | 0 | 0 | undefined |
| weak-distributed | 16 | 4 | 0 | 0 | 12 | 0.4 |

## Numerical and operational scope

MAE/MSE/RMSE apply only to matched synthetic event-onset time because that is the only continuous target with independent truth. QuakeMesh does not estimate earthquake magnitude or epicentre. Binary-prediction MAE/MSE would merely restate classification error and is therefore not presented. Local processing timings exclude AWS and network time. AWS latency, cost, SNS acceptance, FCM receipt, notification display, and physical corroboration remain `NOT_RUN`.

## Reproduction and limitations

Run `python scripts/run_research_evaluation.py --output results/research-evaluation`. The manifest retains every seed and effective detector/network/spatial parameter. Scenario semantics are fixed independently of detector output. Synthetic accelerometer-feature injection measures rule implementation behavior, not population earthquake sensitivity. The benchmark includes deliberate confounders and boundary conditions but does not model structural coupling, regional geology, handset mounting, synchronized human behavior prevalence, or real-world sampling bias.
