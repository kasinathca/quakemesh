from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from evaluation.runner import ExperimentConfig, run_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline synthetic QuakeMesh detector evaluation")
    parser.add_argument("--output", default="artifacts/evaluation/latest")
    parser.add_argument("--trials-per-scenario", type=int, default=8)
    parser.add_argument("--base-seed", type=int, default=20261019)
    parser.add_argument("--publish-dashboard", action="store_true")
    args = parser.parse_args()
    if args.trials_per_scenario < 1:
        parser.error("--trials-per-scenario must be positive")
    output = Path(args.output)
    summary = run_experiment(output, ExperimentConfig(args.trials_per_scenario, args.base_seed))
    if args.publish_dashboard:
        target = Path("dashboard/public/evaluation")
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output / "summary.json", target / "latest.json")
        shutil.copy2(output / "trials.csv", target / "trials.csv")
        shutil.copy2(output / "trials.json", target / "trials.json")
    print(json.dumps({"output": str(output), "trial_counts": summary["trial_counts"], "confusion_matrix": summary["confusion_matrix"], "metrics": summary["metrics"]}, indent=2))
    return 0 if summary["trial_counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
