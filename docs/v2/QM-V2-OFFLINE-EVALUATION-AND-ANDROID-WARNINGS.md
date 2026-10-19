# QuakeMesh V2 offline evaluation and Android warning UX

**Status:** locally implemented and repeatably testable

**Scope:** synthetic software evaluation and Android notification presentation
**Safety:** no AWS deployment, infrastructure mutation, or detector-threshold change is part of this work

## Research evaluation contract

`scripts/run_evaluation.py` runs independent trials against the same `QuakeMeshService`, correlation functions, default `DetectionConfig`, SQLite persistence, and production `H3GeoIndex` used by the local application. It does not implement an easier surrogate classifier. Every trial starts with a fresh database and device identity namespace.

Injected truth is held by the evaluator only. It is never added to heartbeat or trigger payloads. `isolated` and `same-cell` are negative event labels; `distributed` and `degraded` are positive event labels. A positive prediction exists only when the detector creates a confirmed event. This yields an event-level TP/TN/FP/FN matrix rather than a per-packet matrix.

The default deterministic matrix varies:

- 12 independent seeds per scenario (48 trials), beginning at seed `20261019`;
- 12- and 25-device fleets;
- Bengaluru-area centers with deterministic latitude/longitude variation of up to `0.018` degrees;
- grid spacing multipliers `0.8`, `1.0`, and `1.2` around the established `0.012` degree spacing;
- propagation intervals of 40, 70, and 120 ms;
- maximum network jitter of 0, 150, 600, and 1200 ms;
- degraded-trial packet-loss fractions of 0, 0.15, 0.30, and 0.45;
- deterministic motion amplitudes above the existing motion gate, without changing any corroboration threshold.

Network delay changes arrival order. Packet loss removes selected trigger observations before ingress. The detector sees only delivered observation payloads. Confirmation latency is logical simulated elapsed time between the first injected trigger observation and the delivery that first causes a local confirmed event. Alert-target latency ends when the synchronous local runtime creates its first authoritative target record. Targeting does not imply transport delivery, and neither targeting nor a Firebase send implies notification receipt.

The output separates:

1. injected scenario truth;
2. local production-detector confirmation;
3. cloud confirmation, explicitly `NOT_RUN_OFFLINE`;
4. local authoritative alert targeting;
5. actual notification receipt, explicitly `NOT_OBSERVED_OFFLINE`.

Ratios use explicit JSON `null` for zero denominators. Accuracy, precision, recall, specificity, F1, false-positive rate, false-negative rate, and transport delivery ratio include two-sided 95% Wilson intervals. Mean latencies include deterministic 2,000-resample percentile-bootstrap intervals. Every seed and condition is retained in per-trial CSV and JSON.

## Measured local batch — 2026-10-19

The 48-trial default batch completed with zero runner failures using h3-py 4.5.0 and the unchanged detector thresholds.

| Injected truth | Detector positive | Detector negative |
|---|---:|---:|
| Positive | TP 24 | FN 0 |
| Negative | FP 0 | TN 24 |

| Metric | Measured result | 95% Wilson interval |
|---|---:|---:|
| Accuracy | 1.0000 | 0.9259–1.0000 |
| Precision | 1.0000 | 0.8620–1.0000 |
| Recall | 1.0000 | 0.8620–1.0000 |
| Specificity | 1.0000 | 0.8620–1.0000 |
| F1 | 1.0000 | 0.9259–1.0000 |
| False-positive rate | 0.0000 | 0.0000–0.1380 |
| False-negative rate | 0.0000 | 0.0000–0.1380 |

Mean confirmation and target latency were both 513.75 ms (median 469.5 ms). Their equality is expected in the synchronous local runtime and must not be generalized to AWS or FCM. The injected transport delivered 311 of 348 trigger observations, a ratio of 0.8937 (95% Wilson interval 0.8569–0.9219). All four configured degraded-condition groups classified correctly in this finite batch, but each group has only three trials and a wide group-level interval (0.4385–1.0000).

These are **synthetic simulation results**, not field sensitivity/specificity and not real-world earthquake-detection accuracy. The trial set does not model sensor orientation diversity, building response, soil response, human activity distributions, hardware heterogeneity, or independently labeled earthquake recordings.

Generated outputs are under `artifacts/evaluation/latest/` for the local run. Publishable dashboard copies are in `dashboard/public/evaluation/`: `latest.json`, `trials.json`, and `trials.csv`. A curated, tracked report snapshot is in `results/offline-evaluation/` and contains `summary.json`, `trials.csv`, `robustness.csv`, `REPORT.md`, `confusion-matrix.svg`, and `robustness-by-network.svg`. Raw local artifacts remain ignored and reproducible.

## Dashboard

The `Evaluation / Metrics` view loads the generated offline artifacts independently of the operational API. Scenario and network-condition filters recompute visible event-level metrics. CSV and JSON exports contain the filtered trials. PNG export renders the filtered confusion matrix. The existing Scenario Lab and AWS operational views are unchanged; no unavailable AWS telemetry is synthesized.

## Android warning and preview contract

Three versioned channels are used:

- `quakemesh_monitoring_v1`: low importance, no sound, no vibration;
- `quakemesh_warnings_v2`: high importance, original warning tone, long vibration pattern;
- `quakemesh_controlled_demo_v1`: high importance, a different original preview tone and shorter vibration pattern.

The two WAV files are deterministically synthesized by `scripts/generate_android_tones.py`, use no third-party samples, and are documented in `android/NOTICE-notification-tones.md`.

Notification taps open `WarningActivity`, which presents status, physical/scenario/test provenance, supplied H3 warning cells, event/alert identity, timestamp, detail navigation, and dismissal. Two debug-only buttons create local controlled previews for the demonstration and warning tones with `authoritativeRecord=false`; neither calls AWS, stores a fake cloud event, or exposes an ACK action. A debug-manifest-only explicit broadcast receiver supports repeatable foreground/background ADB verification and uses the same delivery-deduplication store as `FirebaseMessagingService`; it is absent from release builds. ACK remains limited to authoritative alert records. Existing FCM deduplication, token registration through heartbeat, polling fallback, and API acknowledgement remain intact.

QuakeMesh deliberately does not request or attach a full-screen intent. Current Android restricts that capability to user/OS-approved use cases such as alarms and calls, and QuakeMesh must not bypass those controls. High-importance heads-up notification is the fallback; its actual appearance remains subject to the installed channel and user notification settings.

### Physical local verification — Motorola `ZD222HDG42`, Android API 35

The LOCAL/DEFAULT Firebase-enabled debug APK was reinstalled with `-r` and its existing application-state hash remained unchanged. Foreground and background controlled previews were posted through `quakemesh_controlled_demo_v1` and `quakemesh_warnings_v2`. Android's notification service recorded importance `HIGH`, two distinct bundled resource URIs, alarm audio usage, and distinct vibration patterns. The warning preview stayed in the background and did not attempt automatic full-screen launch.

The notification shade showed the explicit `CONTROLLED QuakeMesh preview` and `not an earthquake alert` labels. Tapping it opened `WarningActivity`; the activity visibly contained controlled-test status/provenance, H3 fallback, event/alert IDs, timestamp, View details, Dismiss, and an unavailable-ACK explanation. View details navigated to `MainActivity`. Redelivery of the same stable ID returned `duplicate-suppressed` and retained one notification record. The authoritative state-file hash was unchanged across previews.

On this device, no heads-up overlay was visible in timed foreground or background UI captures. The system had global heads-up enabled, channel importance `HIGH`, no DND interception, and no suppressed visual effects, but the notification record reported `mIsInterruptive=false`. Therefore notification-shade delivery and tap navigation are verified, while heads-up display is **OS/OEM-restricted under the current device settings/state**. The tooling can prove that both sound resources were selected and submitted to Android, but cannot objectively hear the handset speaker; audible-volume confirmation remains a human observation.

## Reproduction

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --output artifacts\evaluation\latest --trials-per-scenario 12 --base-seed 20261019 --publish-dashboard
```

The command is offline and creates no AWS resources.
