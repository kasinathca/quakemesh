from evaluation.metrics import classification_metrics, error_metrics, poisson_rate_interval, safe_ratio
from evaluation.research import ResearchConfig, match_events, trial_specs as research_trial_specs
from evaluation.recorded import evaluate_uci_har
from evaluation.runner import ExperimentConfig, run_experiment, trial_specs
import zipfile


def test_zero_denominators_are_explicitly_undefined():
    metrics = classification_metrics(0, 4, 0, 0)
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["specificity"] == 1.0
    assert safe_ratio(0, 0) is None


def test_extended_classification_and_continuous_error_metrics():
    metrics = classification_metrics(8, 7, 2, 3)
    assert metrics["f2"] == 40 / 54
    assert metrics["balanced_accuracy"] == ((8 / 11) + (7 / 9)) / 2
    assert metrics["matthews_correlation_coefficient"] is not None
    errors = error_metrics([100.0, 200.0, 300.0], [110.0, 180.0, 330.0])
    assert errors["mae"] == 20.0
    assert errors["mse"] == 1400 / 3
    assert errors["rmse"] is not None
    assert poisson_rate_interval(0, 2.0) == [0.0, -__import__("math").log(0.025) / 2.0]
    assert poisson_rate_interval(3, 0) is None


def test_event_matching_is_one_to_one_and_never_double_counts():
    matched = match_events(
        [{"event_id": "truth-1", "time_ms": 1_000}, {"event_id": "truth-2", "time_ms": 5_000}],
        [{"event_id": "pred-1", "time_ms": 1_050}, {"event_id": "pred-2", "time_ms": 1_100}],
        tolerance_ms=250,
    )
    assert matched["true_positives"] == 1
    assert matched["false_negatives"] == 1
    assert matched["false_positives"] == 1


def test_research_manifest_is_reproducible_and_covers_required_sweeps():
    config = ResearchConfig(trials_per_scenario=16)
    first = research_trial_specs(config)
    assert first == research_trial_specs(config)
    assert len(first) == 320
    assert {row.devices for row in first} == {12, 25, 50, 100}
    assert {row.min_devices for row in first} == {2, 3, 4, 6, 8}
    assert {row.min_distinct_cells for row in first} == {2, 3, 4}
    assert {row.evidence_window_ms for row in first} == {4_000, 8_000, 12_000, 20_000}
    assert {row.packet_loss_fraction for row in first} == {0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90}
    assert {row.jitter_ms for row in first} == {0, 150, 600, 1_200, 2_500, 5_000}
    assert all(row.ground_truth_event_id is None for row in first if not row.truth_positive)


def test_trial_generation_is_reproducible_and_truth_is_external():
    config = ExperimentConfig(trials_per_scenario=2, base_seed=17)
    first = trial_specs(config)
    assert first == trial_specs(config)
    assert {item.scenario for item in first} == {"isolated", "same-cell", "distributed", "degraded"}
    assert [item.truth_positive for item in first if item.scenario == "isolated"] == [False, False]


def test_batch_runs_real_detector_and_writes_machine_readable_outputs(tmp_path):
    output = tmp_path / "evaluation"
    summary = run_experiment(output, ExperimentConfig(trials_per_scenario=1, base_seed=123))
    assert summary["trial_counts"] == {"requested": 4, "completed": 4, "failed": 0}
    assert sum(summary["confusion_matrix"].values()) == 4
    assert summary["reproducibility"]["geo_index"] == "h3-py (real H3)"
    assert summary["notification_receipt"]["observed"] is False
    for name in ("trials.csv", "trials.json", "summary.json", "robustness.csv", "REPORT.md", "confusion-matrix.svg", "robustness-by-network.svg"):
        assert (output / name).is_file()


def test_recorded_dataset_adapter_preserves_subject_partitions(tmp_path):
    archive_path = tmp_path / "uci.zip"
    values = " ".join(["0"] * 128) + "\n"
    z_values = " ".join(["1"] * 128) + "\n"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for split, subject in (("train", 1), ("test", 9)):
            root = f"UCI HAR Dataset/{split}/"
            signals = root + "Inertial Signals/"
            archive.writestr(signals + f"total_acc_x_{split}.txt", values)
            archive.writestr(signals + f"total_acc_y_{split}.txt", values)
            archive.writestr(signals + f"total_acc_z_{split}.txt", z_values)
            archive.writestr(root + f"y_{split}.txt", "1\n")
            archive.writestr(root + f"subject_{split}.txt", f"{subject}\n")
    summary = evaluate_uci_har(archive_path, tmp_path / "recorded", 1)
    assert summary["development"]["windows"] == 1
    assert summary["held_out"]["windows"] == 1
    assert summary["overall"]["false_positive_windows"] == 0
