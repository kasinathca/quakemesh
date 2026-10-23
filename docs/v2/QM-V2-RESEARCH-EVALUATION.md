# QuakeMesh V2 research evaluation and controlled wireless delivery

**Status:** the benchmark in this document is offline by design. Later final-system AWS and physical-device validation is recorded separately in `QM-V2-FINAL-DEMO-VALIDATION.md`; the scopes are not combined into an accuracy claim.

## Architecture and change boundary

The production detector remains rule based and unchanged by this work. Android extracts orientation-invariant acceleration-magnitude deviation features; ingress requires RMS ≥ 0.75 m/s² and peak ≥ 1.80 m/s² by default; correlation retains the latest observation per physical device in an 8 s window and requires four devices in three connected H3 resolution-7 cells. The benchmark calls the production `QuakeMeshService`, `DetectionConfig`, motion gate, persistence, correlation and `H3GeoIndex`; it does not substitute a model. Production defaults remain unchanged.

The original 48-trial result under `results/offline-evaluation/` is immutable historical evidence and remains selectable in the dashboard. The expanded benchmark is under `results/research-evaluation/`. Recorded human-activity gate results are under `results/recorded-negative-evaluation/`. Synthetic, recorded, local, AWS and handset evidence are never combined into one accuracy claim.

## Ground truth and matching

Scenario definitions assign ground truth before execution. Labels, truth event IDs and truth times exist only in the evaluator manifest and are not sent to the detector. A nearest-time greedy matcher pairs ground-truth and predicted events one-to-one within a configurable 10 s tolerance. A matched pair is one TP; unmatched truth is FN; an unmatched confirmation is FP. A negative trial with no confirmation is TN. Event IDs deduplicate repeated detector output. Failed executions are reported separately and never counted as negative predictions.

Negative exposure is the configured evidence window plus injected jitter and scenario duration. False alarms per observation hour use only valid negative exposure. Logical simulation timestamps are not AWS wall-clock measurements.

## Benchmark design

The default run contains 320 independently seeded event-level trials: 16 trials for each of 20 scenario types. Positive cases cover strong, weak and near-threshold distributed motion; partial participation; low density; network-loss-induced insufficient evidence; delayed/out-of-order delivery; orientation/noise variation; and H3-boundary layouts. Negative cases cover isolated shaking, walking, cycling, handling, drops, repeated single-device vibration, same-cell devices, uncorrelated locations, coordinated human quorum, replay/staleness and near-threshold noise.

The manifest records 12/25/50/100 devices; 2/3/4/6/8 minimum devices; 2/3/4 minimum cells; 4/8/12/20 s windows; 0/15/30/45/60/75/90% loss; 0/150/600/1200/2500/5000 ms jitter; RMS thresholds 0.60/0.75/0.90 m/s²; peak thresholds 1.45/1.80/2.15 m/s²; dense/sparse/boundary/irregular layouts; four noise levels; participation; and exact seeds. Loss and jitter are explicit paired fields, not a single conflated “network quality” variable. Rotating designed sweeps avoid an infeasible full Cartesian product while ensuring every requested level occurs. Every fifth ordinal is reserved as held out before execution. No threshold fitting is performed.

The completed default run had zero execution failures and produced TP=86, TN=151, FP=25 and FN=58. Aggregate accuracy was 0.7406 (95% CI 0.6899–0.7856), precision 0.7748 (0.6886–0.8425), recall 0.5972 (0.5156–0.6738), specificity 0.8580 (0.7987–0.9019), F1 0.6745 (0.6148–0.7291), balanced accuracy 0.7276 and MCC 0.4758. The pre-reserved 60-trial held-out partition produced TP=18, TN=28, FP=5 and FN=9; accuracy 0.7667 (0.6456–0.8556), F1 0.7200 (0.5833–0.8253), balanced accuracy 0.7576 and MCC 0.5271. These non-perfect results arose from the independently designed boundary conditions and confounders; no label or prediction was altered to create errors.

## Metrics

For counts TP, TN, FP and FN:

- accuracy = (TP + TN) / N;
- precision or PPV = TP / (TP + FP);
- recall or sensitivity = TP / (TP + FN);
- specificity = TN / (TN + FP);
- F1 = 2TP / (2TP + FP + FN);
- F2 = 5TP / (5TP + 4FN + FP);
- false-positive rate = FP / (FP + TN);
- false-negative rate = FN / (FN + TP);
- negative predictive value = TN / (TN + FN);
- balanced accuracy = (recall + specificity) / 2;
- MCC = (TP×TN − FP×FN) / √((TP+FP)(TP+FN)(TN+FP)(TN+FN)).

Zero denominators serialize as `null`. Proportion intervals are two-sided 95% Wilson intervals; false alarms per observation hour use a two-sided 95% Poisson-rate interval (Byar approximation). Per-scenario and aggregate values, confusion matrices, sample sizes and scopes are machine readable. ROC-AUC and PR-AUC are intentionally absent because the current detector emits a hard decision rather than a calibrated continuous event score.

MAE, MSE, RMSE, median absolute error and error percentiles are calculated only for matched synthetic event-onset timing. QuakeMesh does not estimate magnitude or epicentre, so no such error is claimed. Applying MAE/MSE to binary outputs would merely re-express classification error and is not scientifically useful.

## Recorded smartphone data

The recorded negative evaluation uses the UCI Human Activity Recognition Using Smartphones dataset (DOI `10.24432/C54S4K`, CC BY 4.0). It contains video-labeled activities from 30 people wearing a Samsung Galaxy S II at the waist. Triaxial accelerometer and gyroscope data were sampled at 50 Hz in 128-sample, 2.56 s windows. The adapter reads `total_acc`, converts standard-gravity units to m/s², and passes each real accelerometer window through production `extract_motion_features` and `passes_motion_gate`. Vector magnitude is orientation invariant. The original subject-disjoint train/test split is retained as development/held-out.

These recordings are authentic negative human activity, but they are not synchronized across phones and therefore cannot defensibly test the spatial event correlator. The report presents single-device motion-gate false-trigger rates, not earthquake accuracy. UCI’s activities omit cycling, drops and many real placements. No raw archive is committed.

The executed 2,000-window sample retained 1,000 development and 1,000 held-out windows. On held-out subjects, 469/1,000 negative windows passed the local motion gate: rate 0.4690, 95% Wilson interval 0.4382–0.5000. Walking, upstairs and downstairs windows all passed in this finite sample; sitting and standing windows did not; 4/347 laying windows passed overall. This is expected evidence that the local amplitude gate is not a human-activity classifier. Spatial/temporal corroboration is essential, and the result must not be read as a 46.9% event false-alarm rate.

Public MyShake research demonstrates that phones can record earthquake motion, but waveform access is constrained by privacy in relevant publications. A small public MyShake parametric ground-motion database exists, but it contains event-level peak parameters rather than raw triaxial windows compatible with QuakeMesh feature extraction, and its Zenodo page did not display a license during this review. It was therefore documented but not transformed into purported raw-phone detector trials. Conventional seismometer waveforms are also not relabeled as smartphone accelerometer data.

Sources: [UCI HAR dataset](https://archive.ics.uci.edu/dataset/240/human%2Bactivity%2Brecogni-tion%2Busing%2Bsmartphones), [MyShake system paper](https://doi.org/10.1126/sciadv.1501055), [MyShake parametric database](https://doi.org/10.5281/zenodo.13288173), and [MyShake waveform availability statement](https://doi.org/10.3390/s23218668).

## Controlled wireless notification architecture

Controlled delivery is separate from corroboration:

`dashboard → operator-key API route → session-owned physical device lookup → SNS/FCM → Android receipt telemetry`

The dashboard supplies only a device ID and stable test-message ID. It cannot submit an SNS endpoint ARN. The API requires a separate session operator API key ID, distinct from the API key embedded in Android builds. It verifies physical provenance, exact session ownership, a heartbeat within 120 s and an existing FCM endpoint; suppresses idempotent repeats; and rate-limits new per-device tests to one every 30 s. Frontend responses remove endpoint ARNs, FCM tokens and SNS message IDs.

Deployment writes the operator key only to the ignored session `runtime-config.json` as `operator_api_key`; it is not copied into dashboard `config.js` or Android `local.properties`. An operator pastes it into the dashboard's in-memory password field for the controlled action. The field is not persisted by the application.

The alert table records non-authoritative controlled-test states: `REQUESTED`, `SNS_ACCEPTED`, `FCM_RECEIVED`, `NOTIFICATION_POSTED`, `OPENED` or `FAILED`. SNS acceptance is not handset receipt. Android posts the last three transitions using its configured session API key and exact device/test binding. Every payload and display contains **CONTROLLED TEST — NOT AN EARTHQUAKE ALERT**, uses the controlled channel, and cannot be acknowledged as an earthquake alert. Stable alert IDs preserve deduplication. Notification taps open `WarningActivity` and report `OPENED` without using a full-screen intent.

Android 13+ notification permission and device/OEM channel policy still control visible presentation. High importance is requested, but a heads-up overlay is not guaranteed. The acceptance target is notification-shade delivery and navigation.

## Cloud performance and lifecycle status

The result schema has separate fields for API, ingestion, Lambda, correlation, dispatch, SNS and physical receipt timing. This offline revision reports them as `NOT_RUN`; local logical timestamps are never presented as cloud latency. Cost per workload also remains unmeasured pending an explicitly authorized deployment.

The missed 2026-10-19 automatic expiry was investigated offline. Cleanup performs multiple guarded IoT calls per simulator sequentially; the earlier 60 s Lambda timeout was not defensible for the verified 25-device fleet and is the leading unproven failure explanation. The timeout is now 600 s with 512 MB. Ownership checks, exact-stack deletion and manual STOP remain unchanged. A real scheduled-expiry run is still required before claiming repair.

## Reproduction

```powershell
$env:PYTHONPATH="$PWD\src;$PWD"
.\.venv\Scripts\python.exe scripts\run_evaluation.py --output results\offline-evaluation --trials-per-scenario 12 --base-seed 20261019
.\.venv\Scripts\python.exe scripts\run_research_evaluation.py --output results\research-evaluation --trials-per-scenario 16 --base-seed 20261022 --publish-dashboard
.\.venv\Scripts\python.exe scripts\run_recorded_evaluation.py --download --max-windows-per-split 1000
```

The first two commands are offline. The third downloads the 58.2 MB CC BY 4.0 archive into ignored `artifacts/datasets/`; it does not deploy AWS. Live AWS/FCM and physical corroboration require separate authorization and multiple independent physical phones. One phone cannot satisfy the four-device/three-cell default quorum, and simulator evidence is never mixed with physical evidence.
