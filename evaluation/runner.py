from __future__ import annotations

import csv
import json
import random
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from local_runtime.repository import SQLiteRepository
from local_runtime.service import QuakeMeshService
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex
from simulator.fleet import Fleet

from .metrics import classification_metrics, percentile_interval, safe_ratio, wilson_interval


SCENARIO_TRUTH = {
    "isolated": False,
    "same-cell": False,
    "distributed": True,
    "degraded": True,
}


@dataclass(frozen=True)
class ExperimentConfig:
    trials_per_scenario: int = 8
    base_seed: int = 20261019
    device_counts: tuple[int, ...] = (12, 25)
    degraded_loss_fractions: tuple[float, ...] = (0.0, 0.15, 0.30, 0.45)
    jitter_ms_values: tuple[int, ...] = (0, 150, 600, 1200)
    propagation_ms_values: tuple[int, ...] = (40, 70, 120)
    spacing_scales: tuple[float, ...] = (0.8, 1.0, 1.2)
    center_lat: float = 12.9716
    center_lon: float = 77.5946
    center_variation_deg: float = 0.018


@dataclass(frozen=True)
class TrialSpec:
    trial_id: str
    scenario: str
    truth_positive: bool
    seed: int
    devices: int
    packet_loss_fraction: float
    jitter_ms: int
    propagation_interval_ms: int
    center_lat: float
    center_lon: float
    spacing_deg: float


def trial_specs(config: ExperimentConfig) -> list[TrialSpec]:
    specs: list[TrialSpec] = []
    for scenario_index, scenario in enumerate(SCENARIO_TRUTH):
        for ordinal in range(config.trials_per_scenario):
            seed = config.base_seed + scenario_index * 100_003 + ordinal
            rng = random.Random(seed)
            loss = config.degraded_loss_fractions[ordinal % len(config.degraded_loss_fractions)] if scenario == "degraded" else 0.0
            specs.append(TrialSpec(
                trial_id=f"{scenario}-{ordinal + 1:03d}-s{seed}",
                scenario=scenario,
                truth_positive=SCENARIO_TRUTH[scenario],
                seed=seed,
                devices=config.device_counts[ordinal % len(config.device_counts)],
                packet_loss_fraction=loss,
                jitter_ms=config.jitter_ms_values[ordinal % len(config.jitter_ms_values)],
                propagation_interval_ms=config.propagation_ms_values[ordinal % len(config.propagation_ms_values)],
                center_lat=config.center_lat + rng.uniform(-config.center_variation_deg, config.center_variation_deg),
                center_lon=config.center_lon + rng.uniform(-config.center_variation_deg, config.center_variation_deg),
                spacing_deg=0.012 * config.spacing_scales[ordinal % len(config.spacing_scales)],
            ))
    return specs


def _trigger_indices(scenario: str, count: int) -> list[int]:
    if scenario == "isolated":
        return [0]
    if scenario == "same-cell":
        return list(range(min(6, count)))
    if scenario == "distributed":
        return list(range(min(8, count)))
    return list(range(min(16, count)))


def _run_trial(spec: TrialSpec, detector_config: DetectionConfig, database: Path) -> dict[str, Any]:
    rng = random.Random(spec.seed)
    geo = H3GeoIndex()
    repository = SQLiteRepository(database)
    service = QuakeMeshService(repository, geo, detector_config)
    phones = Fleet.around(spec.devices, spec.center_lat, spec.center_lon, spec.spacing_deg, f"QM-EVAL-{spec.seed}")
    if spec.scenario == "same-cell":
        anchor = (phones[0].latitude, phones[0].longitude)
        for phone in phones[:6]:
            phone.latitude, phone.longitude = anchor

    base_ms = 1_800_000_000_000 + (spec.seed % 10_000_000) * 10_000
    for phone in phones:
        service.heartbeat({
            "schema_version": "1.0", "device_id": phone.device_id,
            "seq": phone.next_seq(), "observed_at_ms": base_ms,
            "latitude": phone.latitude, "longitude": phone.longitude,
        })

    attempted = []
    delivered = []
    for ordinal, index in enumerate(_trigger_indices(spec.scenario, len(phones))):
        phone = phones[index]
        observed_at = base_ms + 1_000 + ordinal * spec.propagation_interval_ms
        network_delay = rng.randint(0, spec.jitter_ms) if spec.jitter_ms else 0
        item = (observed_at + network_delay, ordinal, phone, observed_at, network_delay)
        attempted.append(item)
        if rng.random() >= spec.packet_loss_fraction:
            delivered.append(item)
    delivered.sort(key=lambda item: (item[0], item[1]))

    confirmed_at: int | None = None
    targeted_at: int | None = None
    event_ids: set[str] = set()
    target_devices: set[str] = set()
    accepted = 0
    processing_ms = 0.0
    first_observed = attempted[0][3]
    for delivery_at, _ordinal, phone, observed_at, _network_delay in delivered:
        started = time.perf_counter_ns()
        result = service.trigger({
            "schema_version": "1.0", "device_id": phone.device_id,
            "seq": phone.next_seq(), "observed_at_ms": observed_at,
            "latitude": phone.latitude, "longitude": phone.longitude,
            "motion_rms": round(rng.uniform(1.0, 1.8), 4),
            "motion_peak": round(rng.uniform(2.0, 3.2), 4),
        }, received_at_ms=delivery_at)
        processing_ms += (time.perf_counter_ns() - started) / 1_000_000
        accepted += int(bool(result.get("accepted")))
        if event := result.get("event"):
            event_ids.add(str(event["event_id"]))
            confirmed_at = delivery_at if confirmed_at is None else min(confirmed_at, delivery_at)
        targets = result.get("new_alert_devices", [])
        if targets:
            target_devices.update(str(value) for value in targets)
            targeted_at = delivery_at if targeted_at is None else min(targeted_at, delivery_at)

    predicted_positive = bool(event_ids)
    return {
        **asdict(spec),
        "label_source": "injected_scenario_truth_not_sent_to_detector",
        "prediction_source": "production_QuakeMeshService_with_h3_py",
        "predicted_positive": predicted_positive,
        "outcome": "TP" if spec.truth_positive and predicted_positive else "FN" if spec.truth_positive else "FP" if predicted_positive else "TN",
        "attempted_triggers": len(attempted),
        "delivered_triggers": len(delivered),
        "accepted_evidence": accepted,
        "transport_delivery_success_ratio": safe_ratio(len(delivered), len(attempted)),
        "local_detector_confirmation_observed": predicted_positive,
        "cloud_confirmation_observed": None,
        "cloud_confirmation_status": "NOT_RUN_OFFLINE",
        "confirmation_latency_ms": None if confirmed_at is None else confirmed_at - first_observed,
        "alert_targeting_observed": bool(target_devices),
        "alert_target_latency_ms": None if targeted_at is None else targeted_at - first_observed,
        "targeted_device_count": len(target_devices),
        "actual_notification_receipt": None,
        "notification_receipt_status": "NOT_OBSERVED_OFFLINE",
        "event_ids": sorted(event_ids),
        "processing_time_ms": round(processing_ms, 3),
        "failure": None,
    }


def _aggregate(trials: list[dict[str, Any]], config: ExperimentConfig, detector_config: DetectionConfig) -> dict[str, Any]:
    completed = [row for row in trials if not row.get("failure")]
    counts = {key: sum(row.get("outcome") == key for row in completed) for key in ("TP", "TN", "FP", "FN")}
    classification = classification_metrics(counts["TP"], counts["TN"], counts["FP"], counts["FN"])
    confirmations = [float(row["confirmation_latency_ms"]) for row in completed if row["confirmation_latency_ms"] is not None]
    alerts = [float(row["alert_target_latency_ms"]) for row in completed if row["alert_target_latency_ms"] is not None]
    attempted = sum(int(row["attempted_triggers"]) for row in completed)
    delivered = sum(int(row["delivered_triggers"]) for row in completed)
    grouped: list[dict[str, Any]] = []
    keys = sorted({(row["scenario"], row["packet_loss_fraction"], row["jitter_ms"]) for row in completed})
    for scenario, loss, jitter in keys:
        rows = [r for r in completed if (r["scenario"], r["packet_loss_fraction"], r["jitter_ms"]) == (scenario, loss, jitter)]
        correct = sum((r["truth_positive"] == r["predicted_positive"]) for r in rows)
        detected = sum(bool(r["predicted_positive"]) for r in rows)
        grouped.append({
            "scenario": scenario, "packet_loss_fraction": loss, "jitter_ms": jitter,
            "trials": len(rows), "correct": correct, "accuracy": safe_ratio(correct, len(rows)),
            "detections": detected, "detection_rate": safe_ratio(detected, len(rows)),
            "accuracy_ci95": wilson_interval(correct, len(rows)),
        })
    return {
        "schema_version": "1.0",
        "result_kind": "OFFLINE_SYNTHETIC_SIMULATION_EVALUATION",
        "disclaimer": "Synthetic scenario results evaluate this software implementation; they are not real-world earthquake-detection accuracy.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reproducibility": {"experiment": asdict(config), "detector": asdict(detector_config), "geo_index": "h3-py (real H3)"},
        "trial_counts": {"requested": len(trials), "completed": len(completed), "failed": len(trials) - len(completed)},
        "confusion_matrix": counts,
        "metrics": classification,
        "latency_ms": {
            "confirmation_count": len(confirmations),
            "confirmation_mean": statistics.fmean(confirmations) if confirmations else None,
            "confirmation_median": statistics.median(confirmations) if confirmations else None,
            "confirmation_mean_ci95": percentile_interval(confirmations),
            "alert_target_count": len(alerts),
            "alert_target_mean": statistics.fmean(alerts) if alerts else None,
            "alert_target_median": statistics.median(alerts) if alerts else None,
            "alert_target_mean_ci95": percentile_interval(alerts, seed=config.base_seed + 1),
        },
        "transport": {
            "attempted_triggers": attempted, "delivered_triggers": delivered,
            "delivery_success_ratio": safe_ratio(delivered, attempted),
            "delivery_success_ci95": wilson_interval(delivered, attempted),
        },
        "notification_receipt": {"observed": False, "reason": "Offline local runtime records targets but has no FCM receipt signal."},
        "robustness": grouped,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def _svg_figures(summary: dict[str, Any], destination: Path) -> None:
    counts = summary["confusion_matrix"]
    maximum = max(1, *counts.values())
    cells = [("TP", 60, 90), ("FN", 250, 90), ("FP", 60, 250), ("TN", 250, 250)]
    rects = []
    for label, x, y in cells:
        opacity = 0.2 + 0.75 * counts[label] / maximum
        rects.append(f'<rect x="{x}" y="{y}" width="170" height="130" rx="8" fill="#126e82" fill-opacity="{opacity:.3f}"/><text x="{x+85}" y="{y+55}" text-anchor="middle" font-size="22" font-weight="700">{label}</text><text x="{x+85}" y="{y+92}" text-anchor="middle" font-size="32">{counts[label]}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="440" viewBox="0 0 500 440"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:Arial,sans-serif;fill:#172b35}}</style><text x="250" y="32" text-anchor="middle" font-size="22" font-weight="700">Offline synthetic event-level confusion matrix</text><text x="250" y="58" text-anchor="middle" font-size="13">Actual QuakeMesh detector · real H3 · n={summary['trial_counts']['completed']}</text><text x="18" y="230" transform="rotate(-90 18 230)" text-anchor="middle" font-size="14">Injected truth</text><text x="250" y="425" text-anchor="middle" font-size="14">Detector prediction</text><text x="145" y="80" text-anchor="middle">Positive</text><text x="335" y="80" text-anchor="middle">Negative</text><text x="48" y="158" text-anchor="end">Positive</text><text x="48" y="318" text-anchor="end">Negative</text>{''.join(rects)}<text x="250" y="398" text-anchor="middle" font-size="11">Synthetic software evaluation — not real-world earthquake accuracy</text></svg>'''
    (destination / "confusion-matrix.svg").write_text(svg, encoding="utf-8")

    groups = summary["robustness"]
    width, height = 900, 460
    bars = []
    for index, row in enumerate(groups):
        value = float(row["accuracy"] or 0)
        condition_label = f"{row['scenario']} L{row['packet_loss_fraction']} J{row['jitter_ms']}"
        x = 70 + index * max(22, 760 / max(1, len(groups)))
        bar_width = max(12, 650 / max(1, len(groups)))
        y = 380 - value * 280
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{value*280:.1f}" fill="#d45b3f"/><text x="{x+bar_width/2:.1f}" y="{y-5:.1f}" text-anchor="middle" font-size="10">{value:.2f}</text><text x="{x+bar_width/2:.1f}" y="395" transform="rotate(55 {x+bar_width/2:.1f} 395)" font-size="9">{condition_label}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:Arial,sans-serif;fill:#172b35}}</style><text x="450" y="30" text-anchor="middle" font-size="22" font-weight="700">Robustness by synthetic network condition</text><line x1="60" y1="100" x2="60" y2="380" stroke="#566"/><line x1="60" y1="380" x2="850" y2="380" stroke="#566"/><text x="22" y="240" transform="rotate(-90 22 240)" text-anchor="middle">Event classification accuracy</text>{''.join(bars)}<text x="450" y="452" text-anchor="middle" font-size="11">Scenario · packet loss fraction · maximum jitter (ms)</text></svg>'''
    (destination / "robustness-by-network.svg").write_text(svg, encoding="utf-8")


def _report(summary: dict[str, Any], destination: Path) -> None:
    m, c, latency = summary["metrics"], summary["confusion_matrix"], summary["latency_ms"]
    def fmt(value: Any) -> str:
        return "undefined (zero denominator)" if value is None else f"{float(value):.4f}"
    text = f"""# QuakeMesh offline synthetic evaluation report

> **Simulation result only.** These measurements evaluate deterministic synthetic scenarios against the QuakeMesh software detector. They are not estimates of real-world earthquake-detection accuracy.

Generated: {summary['generated_at']}

Trials: {summary['trial_counts']['completed']} completed / {summary['trial_counts']['requested']} requested; {summary['trial_counts']['failed']} failed.

## Event-level confusion matrix

| | Predicted positive | Predicted negative |
|---|---:|---:|
| Injected positive | TP {c['TP']} | FN {c['FN']} |
| Injected negative | FP {c['FP']} | TN {c['TN']} |

| Metric | Value |
|---|---:|
| Accuracy | {fmt(m['accuracy'])} |
| Precision | {fmt(m['precision'])} |
| Recall | {fmt(m['recall'])} |
| Specificity | {fmt(m['specificity'])} |
| F1 | {fmt(m['f1'])} |
| False-positive rate | {fmt(m['false_positive_rate'])} |
| False-negative rate | {fmt(m['false_negative_rate'])} |

All ratio confidence intervals in `summary.json` are two-sided 95% Wilson intervals. Undefined zero-denominator metrics are serialized as JSON `null`, never coerced to a perfect or zero score.

## Method

Each trial uses a fresh SQLite database, `QuakeMeshService`, the unchanged `DetectionConfig`, and the production `H3GeoIndex` backed by h3-py. Seeds deterministically control device count, geographic center, grid spacing, trigger motion values, loss, jitter, and arrival order. Isolated and same-cell trials are negative injected truth; distributed and degraded trials are positive injected truth. Truth is retained only by this evaluator and is never included in heartbeat or trigger payloads.

Confirmation latency is logical simulated elapsed time from the first injected trigger observation to the delivery that first yields a confirmed event. Alert-target latency ends at the first local authoritative target record. Mean latency 95% intervals use a deterministic percentile bootstrap. Transport delivery is distinct from targeting. Actual notification receipt is unobserved offline and is never inferred from target creation.

Confirmation latency: mean {fmt(latency['confirmation_mean'])} ms; median {fmt(latency['confirmation_median'])} ms.

Alert-target latency: mean {fmt(latency['alert_target_mean'])} ms; median {fmt(latency['alert_target_median'])} ms.

See `trials.csv`, `trials.json`, `summary.json`, `robustness.csv`, and the SVG figures for reproducible data.
"""
    (destination / "REPORT.md").write_text(text, encoding="utf-8")


def run_experiment(destination: str | Path, config: ExperimentConfig | None = None) -> dict[str, Any]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    config = config or ExperimentConfig()
    detector_config = DetectionConfig()
    trials: list[dict[str, Any]] = []
    # Keep ephemeral databases beside the output. This is sandbox-friendly on
    # Windows and still guarantees a fresh, removed database per batch.
    with TemporaryDirectory(prefix=".working-", dir=destination, ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        for spec in trial_specs(config):
            try:
                trials.append(_run_trial(spec, detector_config, root / f"{spec.trial_id}.db"))
            except Exception as exc:
                trials.append({**asdict(spec), "failure": f"{type(exc).__name__}: {str(exc)[:300]}"})
    summary = _aggregate(trials, config, detector_config)
    (destination / "trials.json").write_text(json.dumps(trials, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(destination / "trials.csv", trials)
    _write_csv(destination / "robustness.csv", summary["robustness"])
    _svg_figures(summary, destination)
    _report(summary, destination)
    return summary
