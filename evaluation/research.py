from __future__ import annotations

import csv
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from local_runtime.repository import SQLiteRepository
from local_runtime.service import QuakeMeshService
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex
from simulator.fleet import Fleet

from .metrics import classification_metrics, error_metrics, poisson_rate_interval, safe_ratio, wilson_interval


SCENARIOS: dict[str, dict[str, Any]] = {
    "strong-distributed": {"truth": True, "family": "intensity", "intensity": "strong"},
    "weak-distributed": {"truth": True, "family": "intensity", "intensity": "weak"},
    "threshold-boundary": {"truth": True, "family": "intensity", "intensity": "boundary"},
    "partial-participation": {"truth": True, "family": "participation", "intensity": "moderate"},
    "low-device-density": {"truth": True, "family": "density", "intensity": "moderate"},
    "network-loss-insufficient": {"truth": True, "family": "network", "intensity": "moderate"},
    "delayed-out-of-order": {"truth": True, "family": "network", "intensity": "moderate"},
    "orientation-and-noise": {"truth": True, "family": "sensor", "intensity": "moderate"},
    "h3-boundary": {"truth": True, "family": "spatial", "intensity": "moderate"},
    "isolated-shaking": {"truth": False, "family": "human-motion", "intensity": "strong"},
    "walking": {"truth": False, "family": "human-motion", "intensity": "weak"},
    "cycling": {"truth": False, "family": "human-motion", "intensity": "weak"},
    "device-handling": {"truth": False, "family": "human-motion", "intensity": "boundary"},
    "phone-drop": {"truth": False, "family": "impact", "intensity": "strong"},
    "repeated-single-device-vibration": {"truth": False, "family": "vibration", "intensity": "strong"},
    "same-cell-multi-device": {"truth": False, "family": "spatial", "intensity": "strong"},
    "uncorrelated-multi-location": {"truth": False, "family": "spatial", "intensity": "strong"},
    "coordinated-human-quorum": {"truth": False, "family": "confounder", "intensity": "strong"},
    "duplicate-replay-stale": {"truth": False, "family": "transport", "intensity": "strong"},
    "near-threshold-noise": {"truth": False, "family": "sensor", "intensity": "boundary"},
}


@dataclass(frozen=True)
class ResearchConfig:
    trials_per_scenario: int = 16
    base_seed: int = 20261022
    matching_tolerance_ms: int = 10_000
    device_counts: tuple[int, ...] = (12, 25, 50, 100)
    min_devices_values: tuple[int, ...] = (2, 3, 4, 6, 8)
    min_cells_values: tuple[int, ...] = (2, 3, 4)
    evidence_windows_ms: tuple[int, ...] = (4_000, 8_000, 12_000, 20_000)
    packet_loss_values: tuple[float, ...] = (0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90)
    jitter_ms_values: tuple[int, ...] = (0, 150, 600, 1_200, 2_500, 5_000)
    rms_threshold_values: tuple[float, ...] = (0.60, 0.75, 0.90)
    peak_threshold_values: tuple[float, ...] = (1.45, 1.80, 2.15)
    spatial_distributions: tuple[str, ...] = ("dense", "sparse", "boundary", "irregular")
    sensor_noise_ms2: tuple[float, ...] = (0.02, 0.08, 0.20, 0.45)


@dataclass(frozen=True)
class TrialSpec:
    trial_id: str
    scenario: str
    scenario_family: str
    partition: str
    truth_positive: bool
    ground_truth_event_id: str | None
    seed: int
    devices: int
    min_devices: int
    min_distinct_cells: int
    evidence_window_ms: int
    packet_loss_fraction: float
    jitter_ms: int
    motion_rms_threshold: float
    motion_peak_threshold: float
    spatial_distribution: str
    sensor_noise_ms2: float
    participation_fraction: float
    matching_tolerance_ms: int


def trial_specs(config: ResearchConfig) -> list[TrialSpec]:
    specs: list[TrialSpec] = []
    for scenario_index, (scenario, definition) in enumerate(SCENARIOS.items()):
        for ordinal in range(config.trials_per_scenario):
            seed = config.base_seed + scenario_index * 100_003 + ordinal * 97
            # Pair loss and jitter explicitly while rotating offsets by scenario.
            network_index = ordinal + scenario_index
            packet_loss = config.packet_loss_values[network_index % len(config.packet_loss_values)]
            jitter = config.jitter_ms_values[(network_index * 5) % len(config.jitter_ms_values)]
            if definition["family"] not in {"network", "transport"}:
                packet_loss = config.packet_loss_values[(ordinal // 4) % 3]
                jitter = config.jitter_ms_values[ordinal % 3]
            truth = bool(definition["truth"])
            partition = "held-out" if ordinal % 5 == 4 else "development" if ordinal % 5 == 3 else "design"
            specs.append(TrialSpec(
                trial_id=f"research-{scenario}-{ordinal + 1:03d}-s{seed}",
                scenario=scenario,
                scenario_family=str(definition["family"]),
                partition=partition,
                truth_positive=truth,
                ground_truth_event_id=f"truth-{scenario}-{seed}" if truth else None,
                seed=seed,
                devices=config.device_counts[(ordinal + scenario_index) % len(config.device_counts)],
                min_devices=config.min_devices_values[(ordinal * 2 + scenario_index) % len(config.min_devices_values)],
                min_distinct_cells=config.min_cells_values[(ordinal + scenario_index) % len(config.min_cells_values)],
                evidence_window_ms=config.evidence_windows_ms[(ordinal * 3 + scenario_index) % len(config.evidence_windows_ms)],
                packet_loss_fraction=packet_loss,
                jitter_ms=jitter,
                motion_rms_threshold=config.rms_threshold_values[(ordinal + scenario_index) % len(config.rms_threshold_values)],
                motion_peak_threshold=config.peak_threshold_values[(ordinal * 2 + scenario_index) % len(config.peak_threshold_values)],
                spatial_distribution=config.spatial_distributions[(ordinal + scenario_index) % len(config.spatial_distributions)],
                sensor_noise_ms2=config.sensor_noise_ms2[(ordinal * 3 + scenario_index) % len(config.sensor_noise_ms2)],
                participation_fraction=(0.25, 0.4, 0.6, 0.8, 1.0)[(ordinal + scenario_index) % 5],
                matching_tolerance_ms=config.matching_tolerance_ms,
            ))
    return specs


def match_events(
    ground_truth: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    tolerance_ms: int,
) -> dict[str, Any]:
    """Greedily match nearest event times one-to-one without exposing truth to detection."""
    candidates: list[tuple[int, int, int]] = []
    for truth_index, truth in enumerate(ground_truth):
        for prediction_index, prediction in enumerate(predictions):
            distance = abs(int(prediction["time_ms"]) - int(truth["time_ms"]))
            if distance <= tolerance_ms:
                candidates.append((distance, truth_index, prediction_index))
    matched_truth: set[int] = set()
    matched_predictions: set[int] = set()
    matches: list[dict[str, Any]] = []
    for distance, truth_index, prediction_index in sorted(candidates):
        if truth_index in matched_truth or prediction_index in matched_predictions:
            continue
        matched_truth.add(truth_index)
        matched_predictions.add(prediction_index)
        matches.append({
            "ground_truth_event_id": ground_truth[truth_index]["event_id"],
            "predicted_event_id": predictions[prediction_index]["event_id"],
            "absolute_timing_error_ms": distance,
        })
    return {
        "matches": matches,
        "true_positives": len(matches),
        "false_negatives": len(ground_truth) - len(matched_truth),
        "false_positives": len(predictions) - len(matched_predictions),
    }


def _positions(spec: TrialSpec) -> list[Any]:
    spacing = {"dense": 0.003, "sparse": 0.020, "boundary": 0.010, "irregular": 0.012}[spec.spatial_distribution]
    phones = Fleet.around(spec.devices, 12.9716, 77.5946, spacing, f"QM-RESEARCH-{spec.seed}")
    rng = random.Random(spec.seed ^ 0xA51CE)
    if spec.spatial_distribution == "irregular":
        for phone in phones:
            phone.latitude += rng.uniform(-0.009, 0.009)
            phone.longitude += rng.uniform(-0.009, 0.009)
    if spec.spatial_distribution == "boundary":
        geo = H3GeoIndex()
        cell = geo.cell(12.9716, 77.5946, 7)
        edge = geo.boundary(cell)[0]
        for index, phone in enumerate(phones):
            phone.latitude = edge[0] + ((index % 4) - 1.5) * 0.0035
            phone.longitude = edge[1] + ((index // 4) % 4 - 1.5) * 0.0035
    return phones


def _scenario_plan(spec: TrialSpec, rng: random.Random) -> tuple[list[int], list[tuple[float, float]], int]:
    threshold_rms, threshold_peak = spec.motion_rms_threshold, spec.motion_peak_threshold
    quorum = max(spec.min_devices, spec.min_distinct_cells + 1)
    available = spec.devices
    scenario = spec.scenario
    if scenario in {"isolated-shaking", "phone-drop", "repeated-single-device-vibration"}:
        indices = [0] * (4 if scenario == "repeated-single-device-vibration" else 1)
    elif scenario == "same-cell-multi-device":
        indices = list(range(min(available, quorum + 3)))
    elif scenario == "uncorrelated-multi-location":
        indices = list(range(min(available, quorum + 2)))
    elif scenario == "duplicate-replay-stale":
        indices = [0, 0, 0, 1, 1]
    elif scenario in {"walking", "cycling", "device-handling"}:
        indices = list(range(min(available, max(2, quorum - 1))))
    else:
        desired = max(quorum + 2, int(math.ceil(available * spec.participation_fraction)))
        indices = list(range(min(available, desired)))

    if scenario == "strong-distributed" or scenario in {"phone-drop", "isolated-shaking", "same-cell-multi-device", "uncorrelated-multi-location", "coordinated-human-quorum", "repeated-single-device-vibration", "duplicate-replay-stale"}:
        center = (threshold_rms * 1.65, threshold_peak * 1.55)
    elif scenario in {"weak-distributed", "walking", "cycling"}:
        center = (threshold_rms * 0.88, threshold_peak * 0.90)
    elif scenario in {"threshold-boundary", "device-handling", "near-threshold-noise"}:
        center = (threshold_rms, threshold_peak)
    else:
        center = (threshold_rms * 1.18, threshold_peak * 1.18)
    motion = []
    for _ in indices:
        noise = rng.gauss(0, spec.sensor_noise_ms2)
        motion.append((max(0.001, center[0] + noise), max(0.001, center[1] + noise * 1.8)))
    propagation_ms = 70
    if scenario == "delayed-out-of-order":
        propagation_ms = max(250, spec.evidence_window_ms // max(1, len(indices) - 1))
    elif scenario == "uncorrelated-multi-location":
        propagation_ms = spec.evidence_window_ms + 500
    return indices, motion, propagation_ms


def _run_trial(spec: TrialSpec, database: Path) -> dict[str, Any]:
    rng = random.Random(spec.seed)
    detector = replace(
        DetectionConfig(),
        min_devices=spec.min_devices,
        min_distinct_cells=spec.min_distinct_cells,
        evidence_window_ms=spec.evidence_window_ms,
        motion_rms_threshold=spec.motion_rms_threshold,
        motion_peak_threshold=spec.motion_peak_threshold,
    )
    repository = SQLiteRepository(database)
    service = QuakeMeshService(repository, H3GeoIndex(), detector)
    phones = _positions(spec)
    if spec.scenario == "same-cell-multi-device":
        anchor = (phones[0].latitude, phones[0].longitude)
        for phone in phones:
            phone.latitude, phone.longitude = anchor
    elif spec.scenario == "uncorrelated-multi-location":
        for index, phone in enumerate(phones):
            phone.latitude = 12.0 + index * 0.3
            phone.longitude = 77.0 + index * 0.3

    base_ms = 1_900_000_000_000 + (spec.seed % 1_000_000) * 100_000
    for phone in phones:
        service.heartbeat({
            "schema_version": "1.0", "device_id": phone.device_id, "seq": phone.next_seq(),
            "observed_at_ms": base_ms, "latitude": phone.latitude, "longitude": phone.longitude,
        })
    indices, motion, propagation_ms = _scenario_plan(spec, rng)
    ground_truth_time = base_ms + 1_000
    ground_truth = ([{"event_id": spec.ground_truth_event_id, "time_ms": ground_truth_time}]
                    if spec.truth_positive else [])
    attempted: list[tuple[int, int, Any, int, float, float, int]] = []
    for ordinal, (index, features) in enumerate(zip(indices, motion, strict=True)):
        phone = phones[index]
        observed_at = ground_truth_time + ordinal * propagation_ms
        if spec.scenario == "duplicate-replay-stale" and ordinal == len(indices) - 1:
            observed_at -= detector.max_clock_skew_ms + 1
        delay = rng.randint(0, spec.jitter_ms) if spec.jitter_ms else 0
        attempted.append((observed_at + delay, ordinal, phone, observed_at, features[0], features[1], phone.next_seq()))
    delivered = [item for item in attempted if rng.random() >= spec.packet_loss_fraction]
    if spec.scenario == "delayed-out-of-order":
        delivered.sort(key=lambda item: (-item[0], item[1]))
    else:
        delivered.sort(key=lambda item: (item[0], item[1]))

    predictions_by_id: dict[str, dict[str, Any]] = {}
    accepted = rejected = duplicates = 0
    processing_times: list[float] = []
    rejection_reasons: dict[str, int] = {}
    for delivery_at, ordinal, phone, observed_at, rms, peak, sequence in delivered:
        if spec.scenario == "duplicate-replay-stale" and ordinal in {1, 2}:
            sequence = 2
        started = time.perf_counter_ns()
        try:
            result = service.trigger({
                "schema_version": "1.0", "device_id": phone.device_id, "seq": sequence,
                "observed_at_ms": observed_at, "latitude": phone.latitude, "longitude": phone.longitude,
                "motion_rms": round(rms, 6), "motion_peak": round(peak, 6),
            }, received_at_ms=delivery_at)
        except ValueError as error:
            rejected += 1
            key = type(error).__name__ + ":" + str(error)
            rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
            continue
        processing_times.append((time.perf_counter_ns() - started) / 1_000_000)
        accepted += int(bool(result.get("accepted")))
        rejected += int(not bool(result.get("accepted")))
        duplicates += int(bool(result.get("duplicate_or_replay")))
        if event := result.get("event"):
            predictions_by_id[str(event["event_id"])] = {
                "event_id": str(event["event_id"]),
                "time_ms": int(event["first_observed_at_ms"]),
                "confirmed_at_ms": delivery_at,
            }

    predictions = list(predictions_by_id.values())
    matching = match_events(ground_truth, predictions, spec.matching_tolerance_ms)
    tp, fp, fn = matching["true_positives"], matching["false_positives"], matching["false_negatives"]
    if ground_truth:
        outcome = "TP" if tp else "FN"
    else:
        outcome = "FP" if fp else "TN"
    confirmation_latency = None
    if matching["matches"]:
        match = matching["matches"][0]
        prediction = predictions_by_id[match["predicted_event_id"]]
        confirmation_latency = prediction["confirmed_at_ms"] - ground_truth_time
    exposure_ms = spec.evidence_window_ms + spec.jitter_ms + max(10_000, len(indices) * propagation_ms)
    return {
        **asdict(spec),
        "label_source": "independent_scenario_definition_not_supplied_to_detector",
        "prediction_source": "production_QuakeMeshService_and_H3GeoIndex",
        "ground_truth_time_ms": ground_truth_time if ground_truth else None,
        "predicted_positive": bool(predictions),
        "outcome": outcome,
        "matching": matching,
        "attempted_observations": len(attempted),
        "delivered_observations": len(delivered),
        "accepted_evidence": accepted,
        "rejected_observations": rejected,
        "duplicate_suppressions": duplicates,
        "rejection_reasons": rejection_reasons,
        "transport_delivery_success_ratio": safe_ratio(len(delivered), len(attempted)),
        "confirmation_latency_ms": confirmation_latency,
        "timing_absolute_error_ms": matching["matches"][0]["absolute_timing_error_ms"] if matching["matches"] else None,
        "processing_time_ms": round(sum(processing_times), 6),
        "processing_time_per_observation_ms": statistics.fmean(processing_times) if processing_times else None,
        "negative_exposure_hours": exposure_ms / 3_600_000 if not ground_truth else 0.0,
        "notification_receipt_status": "NOT_OBSERVED_OFFLINE",
        "cloud_measurement_status": "NOT_RUN_OFFLINE",
        "failure": None,
    }


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {key: sum(row.get("outcome") == key for row in rows) for key in ("TP", "TN", "FP", "FN")}


def _metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = _counts(rows)
    metrics = classification_metrics(counts["TP"], counts["TN"], counts["FP"], counts["FN"])
    exposure = sum(float(row.get("negative_exposure_hours", 0)) for row in rows)
    metrics["false_alarms_per_observation_hour"] = safe_ratio(counts["FP"], exposure)
    metrics["false_alarms_per_observation_hour_ci95"] = poisson_rate_interval(counts["FP"], exposure)
    return {"sample_count": len(rows), "confusion_matrix": counts, "metrics": metrics}


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = fraction * (len(values) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] if lower == upper else values[lower] + (values[upper] - values[lower]) * (position - lower)


def _groups(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    values = sorted({row[field] for row in rows}, key=str)
    output = []
    for value in values:
        subset = [row for row in rows if row[field] == value]
        block = _metric_block(subset)
        latencies = [float(row["confirmation_latency_ms"]) for row in subset if row["confirmation_latency_ms"] is not None]
        output.append({
            "dimension": field, "value": value, **block,
            "detection_rate": safe_ratio(sum(bool(row["predicted_positive"]) for row in subset), len(subset)),
            "latency_p50_ms": _percentile(latencies, 0.50),
            "latency_p95_ms": _percentile(latencies, 0.95),
        })
    return output


def _aggregate(trials: list[dict[str, Any]], config: ResearchConfig) -> dict[str, Any]:
    completed = [row for row in trials if not row.get("failure")]
    held_out = [row for row in completed if row["partition"] == "held-out"]
    latencies = [float(row["confirmation_latency_ms"]) for row in completed if row["confirmation_latency_ms"] is not None]
    processing = [float(row["processing_time_per_observation_ms"]) for row in completed if row["processing_time_per_observation_ms"] is not None]
    timing_actual = [float(row["ground_truth_time_ms"]) for row in completed if row["timing_absolute_error_ms"] is not None]
    timing_predicted = [actual + float(row["timing_absolute_error_ms"]) for actual, row in zip(
        timing_actual, [row for row in completed if row["timing_absolute_error_ms"] is not None], strict=True
    )]
    dimensions = [
        "scenario", "packet_loss_fraction", "jitter_ms", "devices", "evidence_window_ms",
        "min_devices", "min_distinct_cells", "motion_rms_threshold", "motion_peak_threshold",
        "spatial_distribution", "sensor_noise_ms2",
    ]
    robustness = [item for dimension in dimensions for item in _groups(completed, dimension)]
    attempted = sum(int(row["attempted_observations"]) for row in completed)
    delivered = sum(int(row["delivered_observations"]) for row in completed)
    accepted = sum(int(row["accepted_evidence"]) for row in completed)
    rejected = sum(int(row["rejected_observations"]) for row in completed)
    duplicates = sum(int(row["duplicate_suppressions"]) for row in completed)
    return {
        "schema_version": "2.0",
        "dataset_id": "quakemesh-research-synthetic-v1",
        "result_kind": "OFFLINE_PHYSICS_INFORMED_SYNTHETIC_RULE_DETECTOR_EVALUATION",
        "measurement_scope": "event-level software simulation; not real-world earthquake accuracy",
        "disclaimer": "Labels are independent scenario semantics. No real earthquake handset ground truth is included.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reproducibility": {
            "experiment": asdict(config),
            "production_detector": "QuakeMeshService with DetectionConfig and h3-py",
            "manifest": "trial-manifest.json",
            "ground_truth_leakage": False,
            "selection_note": "No model fitting or threshold selection was performed; held-out rows were reserved before execution.",
        },
        "trial_counts": {"requested": len(trials), "completed": len(completed), "failed": len(trials) - len(completed), "held_out": len(held_out)},
        **_metric_block(completed),
        "held_out": _metric_block(held_out),
        "per_scenario": _groups(completed, "scenario"),
        "robustness": robustness,
        "latency_ms": {
            "count": len(latencies), "average": statistics.fmean(latencies) if latencies else None,
            "p50": _percentile(latencies, 0.50), "p95": _percentile(latencies, 0.95), "p99": _percentile(latencies, 0.99),
            "scope": "synthetic logical time from injected event onset to local confirmation",
        },
        "processing_ms": {
            "count": len(processing), "average_per_observation": statistics.fmean(processing) if processing else None,
            "p50_per_observation": _percentile(processing, 0.50), "p95_per_observation": _percentile(processing, 0.95),
            "scope": "local wall-clock Python processing; excludes network and AWS",
        },
        "timing_error_ms": {
            **error_metrics(timing_actual, timing_predicted),
            "target": "matched synthetic event onset time",
            "limitation": "QuakeMesh does not estimate magnitude or epicentre; no such errors are reported.",
        },
        "transport": {
            "attempted_observations": attempted, "delivered_observations": delivered,
            "delivery_success_ratio": safe_ratio(delivered, attempted),
            "delivery_success_ci95": wilson_interval(delivered, attempted),
            "accepted_evidence": accepted, "rejected_observations": rejected,
            "duplicate_suppressions": duplicates,
        },
        "cloud": {"status": "NOT_RUN", "reason": "No AWS deployment or live service measurement was authorized."},
        "physical_android": {"status": "NOT_RUN", "reason": "No physical handset result was observed by this offline run."},
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


def _svg_line_chart(path: Path, title: str, rows: list[dict[str, Any]], x_label: str, y_key: str, y_label: str) -> None:
    plotted = [(str(row["value"]), row.get(y_key)) for row in rows if row.get(y_key) is not None]
    width, height = 900, 480
    left, top, plot_width, plot_height = 90, 70, 740, 300
    points = []
    labels = []
    maximum = max(1.0, *(float(raw) for _, raw in plotted))
    for index, (label, raw) in enumerate(plotted):
        x = left + (plot_width * index / max(1, len(plotted) - 1))
        y = top + plot_height * (1 - max(0.0, float(raw)) / maximum)
        points.append(f"{x:.1f},{y:.1f}")
        labels.append(f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" font-size="10">{float(raw):.3g}</text><text x="{x:.1f}" y="395" text-anchor="end" transform="rotate(-35 {x:.1f} 395)" font-size="11">{label}</text>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:Arial,sans-serif;fill:#172b35}}</style><text x="450" y="32" text-anchor="middle" font-size="22" font-weight="700">{title}</text><line x1="{left}" y1="{top}" x2="{left}" y2="{top+plot_height}" stroke="#566"/><line x1="{left}" y1="{top+plot_height}" x2="{left+plot_width}" y2="{top+plot_height}" stroke="#566"/><polyline fill="none" stroke="#126e82" stroke-width="3" points="{' '.join(points)}"/><text x="22" y="220" transform="rotate(-90 22 220)" text-anchor="middle">{y_label}</text><text x="450" y="465" text-anchor="middle">{x_label}</text>{''.join(labels)}<text x="450" y="55" text-anchor="middle" font-size="11">Computed offline trial results; sample counts are in robustness.csv</text></svg>'''
    path.write_text(svg, encoding="utf-8")


def _write_report(summary: dict[str, Any], destination: Path) -> None:
    matrix = summary["confusion_matrix"]
    metrics = summary["metrics"]
    scenario_rows = "\n".join(
        f"| {row['value']} | {row['sample_count']} | {row['confusion_matrix']['TP']} | {row['confusion_matrix']['TN']} | {row['confusion_matrix']['FP']} | {row['confusion_matrix']['FN']} | {row['metrics']['f1'] if row['metrics']['f1'] is not None else 'undefined'} |"
        for row in summary["per_scenario"]
    )
    text = f"""# QuakeMesh research evaluation

> **Scope:** {summary['measurement_scope']}. {summary['disclaimer']}

Generated: {summary['generated_at']}

## Aggregate event-level results

{summary['trial_counts']['completed']} completed trials ({summary['trial_counts']['held_out']} held out); {summary['trial_counts']['failed']} runner failures.

| | Predicted positive | Predicted negative |
|---|---:|---:|
| Ground-truth positive | TP {matrix['TP']} | FN {matrix['FN']} |
| Ground-truth negative | FP {matrix['FP']} | TN {matrix['TN']} |

Accuracy {metrics['accuracy']}; precision {metrics['precision']}; recall {metrics['recall']}; specificity {metrics['specificity']}; F1 {metrics['f1']}; F2 {metrics['f2']}; balanced accuracy {metrics['balanced_accuracy']}; MCC {metrics['matthews_correlation_coefficient']}.

Each proportion includes a two-sided 95% Wilson interval in `summary.json`; undefined denominators remain JSON `null`. MCC is undefined when its denominator is zero. Ground-truth event times are matched one-to-one to the nearest unique detector event within {summary['reproducibility']['experiment']['matching_tolerance_ms']} ms. Unmatched truth is FN, unmatched confirmation is FP, and duplicate alerts do not create additional predictions. Failed executions are excluded and reported separately.

## Scenario results

| Scenario | n | TP | TN | FP | FN | F1 |
|---|---:|---:|---:|---:|---:|---:|
{scenario_rows}

## Numerical and operational scope

MAE/MSE/RMSE apply only to matched synthetic event-onset time because that is the only continuous target with independent truth. QuakeMesh does not estimate earthquake magnitude or epicentre. Binary-prediction MAE/MSE would merely restate classification error and is therefore not presented. Local processing timings exclude AWS and network time. AWS latency, cost, SNS acceptance, FCM receipt, notification display, and physical corroboration remain `NOT_RUN`.

## Reproduction and limitations

Run `python scripts/run_research_evaluation.py --output results/research-evaluation`. The manifest retains every seed and effective detector/network/spatial parameter. Scenario semantics are fixed independently of detector output. Synthetic accelerometer-feature injection measures rule implementation behavior, not population earthquake sensitivity. The benchmark includes deliberate confounders and boundary conditions but does not model structural coupling, regional geology, handset mounting, synchronized human behavior prevalence, or real-world sampling bias.
"""
    (destination / "REPORT.md").write_text(text, encoding="utf-8")


def run_research_experiment(destination: str | Path, config: ResearchConfig | None = None) -> dict[str, Any]:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    config = config or ResearchConfig()
    specs = trial_specs(config)
    (destination / "trial-manifest.json").write_text(json.dumps([asdict(spec) for spec in specs], indent=2, sort_keys=True), encoding="utf-8")
    trials: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix=".working-", dir=destination, ignore_cleanup_errors=True) as temporary:
        root = Path(temporary)
        for spec in specs:
            try:
                trials.append(_run_trial(spec, root / f"{spec.trial_id}.db"))
            except Exception as error:
                trials.append({**asdict(spec), "failure": f"{type(error).__name__}: {str(error)[:500]}"})
    summary = _aggregate(trials, config)
    (destination / "trials.json").write_text(json.dumps(trials, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(destination / "trials.csv", trials)
    _write_csv(destination / "robustness.csv", summary["robustness"])
    _write_csv(destination / "per-scenario.csv", summary["per_scenario"])
    for dimension, filename, y_key, y_label in (
        ("packet_loss_fraction", "f1-vs-packet-loss.svg", "metrics", "F1"),
        ("devices", "recall-vs-device-count.svg", "metrics", "Recall"),
        ("evidence_window_ms", "detection-vs-evidence-window.svg", "detection_rate", "Detection rate"),
        ("motion_rms_threshold", "fpr-vs-rms-threshold.svg", "metrics", "False-positive rate"),
        ("min_distinct_cells", "spatial-diversity-sensitivity.svg", "detection_rate", "Detection rate"),
        ("jitter_ms", "latency-vs-jitter.svg", "latency_p95_ms", "P95 latency (scaled separately)"),
    ):
        rows = [row for row in summary["robustness"] if row["dimension"] == dimension]
        if y_key == "metrics":
            metric_name = "false_positive_rate" if "fpr" in filename else "recall" if "recall" in filename else "f1"
            rows = [{**row, "chart_value": row["metrics"].get(metric_name)} for row in rows]
            chart_key = "chart_value"
        else:
            chart_key = y_key
        _svg_line_chart(destination / filename, filename.removesuffix(".svg").replace("-", " ").title(), rows, dimension, chart_key, y_label)
    _write_report(summary, destination)
    return summary
