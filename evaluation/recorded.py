from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from quakemesh_core.config import DetectionConfig
from quakemesh_core.motion import extract_motion_features, passes_motion_gate

from .metrics import safe_ratio, wilson_interval

UCI_HAR_URL = "https://archive.ics.uci.edu/static/public/240/human+activity+recognition+using+smartphones.zip"
ACTIVITIES = {1: "WALKING", 2: "WALKING_UPSTAIRS", 3: "WALKING_DOWNSTAIRS", 4: "SITTING", 5: "STANDING", 6: "LAYING"}


def download_uci_har(destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(UCI_HAR_URL, headers={"User-Agent": "QuakeMesh research evaluator/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, destination.open("wb") as handle:
        while block := response.read(1024 * 1024):
            handle.write(block)
    return destination


def _rows(archive: zipfile.ZipFile, name: str) -> list[list[float]]:
    with archive.open(name) as handle:
        return [[float(value) for value in line.decode("utf-8").split()] for line in handle]


def _integers(archive: zipfile.ZipFile, name: str) -> list[int]:
    with archive.open(name) as handle:
        return [int(line.decode("utf-8").strip()) for line in handle]


def evaluate_uci_har(archive_path: str | Path, destination: str | Path, max_windows_per_split: int = 1_000) -> dict:
    archive_path, destination = Path(archive_path), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    detector = DetectionConfig()
    trials: list[dict] = []
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    nested: bytes | None = None
    with zipfile.ZipFile(archive_path) as outer:
        if "UCI HAR Dataset.zip" in outer.namelist():
            nested = outer.read("UCI HAR Dataset.zip")
    archive_source: Path | io.BytesIO = io.BytesIO(nested) if nested is not None else archive_path
    with zipfile.ZipFile(archive_source) as archive:
        for split in ("train", "test"):
            prefix = f"UCI HAR Dataset/{split}/"
            inertial = prefix + "Inertial Signals/"
            axes = [_rows(archive, inertial + f"total_acc_{axis}_{split}.txt") for axis in "xyz"]
            labels = _integers(archive, prefix + f"y_{split}.txt")
            subjects = _integers(archive, prefix + f"subject_{split}.txt")
            limit = min(max_windows_per_split, len(labels))
            for index in range(limit):
                samples = [(axes[0][index][sample] * 9.80665, axes[1][index][sample] * 9.80665, axes[2][index][sample] * 9.80665) for sample in range(len(axes[0][index]))]
                features = extract_motion_features(samples)
                triggered = passes_motion_gate(features, detector)
                trials.append({
                    "window_id": f"uci-har-{split}-{index + 1:05d}",
                    "partition": "held-out" if split == "test" else "development",
                    "subject_id": subjects[index],
                    "activity": ACTIVITIES[labels[index]],
                    "sampling_rate_hz": 50,
                    "window_samples": features.sample_count,
                    "window_duration_seconds": features.sample_count / 50,
                    "motion_rms_ms2": features.rms,
                    "motion_peak_ms2": features.peak,
                    "motion_gate_positive": triggered,
                    "truth_positive": False,
                    "outcome": "FP" if triggered else "TN",
                })
    def block(rows: list[dict]) -> dict:
        false_positives = sum(bool(row["motion_gate_positive"]) for row in rows)
        return {
            "windows": len(rows), "false_positive_windows": false_positives,
            "true_negative_windows": len(rows) - false_positives,
            "false_positive_rate": safe_ratio(false_positives, len(rows)),
            "false_positive_rate_ci95": wilson_interval(false_positives, len(rows)),
            "observation_hours": sum(float(row["window_duration_seconds"]) for row in rows) / 3600,
            "false_triggers_per_observation_hour": safe_ratio(false_positives, sum(float(row["window_duration_seconds"]) for row in rows) / 3600),
        }
    by_activity = {activity: block([row for row in trials if row["activity"] == activity]) for activity in ACTIVITIES.values()}
    summary = {
        "schema_version": "1.0", "dataset_id": "uci-har-smartphone-adl",
        "result_kind": "RECORDED_NEGATIVE_MOTION_GATE_EVALUATION",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": UCI_HAR_URL, "doi": "10.24432/C54S4K", "license": "CC BY 4.0",
        "archive_sha256": digest, "sampling_rate_hz": 50, "units": "source total acceleration in standard gravity converted to m/s^2",
        "preprocessing": "128-sample source windows; total_acc x/y/z multiplied by 9.80665 then production extract_motion_features and passes_motion_gate",
        "orientation_handling": "vector magnitude makes the QuakeMesh feature extraction orientation invariant",
        "label_method": "video-labeled activities of daily living; every window is a negative earthquake case",
        "scope": "single-device motion-gate testing only; recordings are not synchronized network events and are not used for event-level earthquake accuracy",
        "detector": asdict(detector), "overall": block(trials),
        "development": block([row for row in trials if row["partition"] == "development"]),
        "held_out": block([row for row in trials if row["partition"] == "held-out"]),
        "by_activity": by_activity,
    }
    (destination / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (destination / "windows.json").write_text(json.dumps(trials, indent=2, sort_keys=True), encoding="utf-8")
    with (destination / "windows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trials[0]) if trials else [])
        if trials:
            writer.writeheader(); writer.writerows(trials)
    held = summary["held_out"]
    activity_rows = "\n".join(
        f"| {activity} | {result['windows']} | {result['false_positive_windows']} | "
        f"{result['false_positive_rate']:.4f} |" if result["false_positive_rate"] is not None
        else f"| {activity} | 0 | 0 | undefined |"
        for activity, result in by_activity.items()
    )
    (destination / "REPORT.md").write_text(f"""# Recorded smartphone negative-case evaluation

Source: UCI Human Activity Recognition Using Smartphones, DOI `10.24432/C54S4K`, CC BY 4.0. Archive SHA-256: `{digest}`.

This evaluates only the QuakeMesh single-device motion gate on authentic video-labeled everyday smartphone accelerometer windows. It is not event-level spatial-correlation performance and not earthquake accuracy.

The held-out subject partition contained {held['windows']} windows: {held['false_positive_windows']} passed the motion gate and {held['true_negative_windows']} did not. Held-out false-positive window rate was {held['false_positive_rate']:.4f} (95% Wilson interval {held['false_positive_rate_ci95'][0]:.4f}–{held['false_positive_rate_ci95'][1]:.4f}). “False positive” here means a negative activity window passed the local motion gate; the multi-device H3 correlator would still need independent spatial quorum.

| Activity | Windows | Gate positives | Gate-positive rate |
|---|---:|---:|---:|
{activity_rows}

Data are 50 Hz, 128-sample windows. Source total acceleration in standard-gravity units is multiplied by 9.80665 and processed by production `extract_motion_features` and `passes_motion_gate`. Raw data remain in ignored `artifacts/datasets/` and are not committed.
""", encoding="utf-8")
    return summary
