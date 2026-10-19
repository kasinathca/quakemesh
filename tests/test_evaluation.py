from evaluation.metrics import classification_metrics, safe_ratio
from evaluation.runner import ExperimentConfig, run_experiment, trial_specs


def test_zero_denominators_are_explicitly_undefined():
    metrics = classification_metrics(0, 4, 0, 0)
    assert metrics["precision"] is None
    assert metrics["recall"] is None
    assert metrics["specificity"] == 1.0
    assert safe_ratio(0, 0) is None


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
