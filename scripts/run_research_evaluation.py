from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from evaluation.research import ResearchConfig, run_research_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the challenging QuakeMesh research benchmark")
    parser.add_argument("--output", default="results/research-evaluation")
    parser.add_argument("--trials-per-scenario", type=int, default=16)
    parser.add_argument("--base-seed", type=int, default=20261022)
    parser.add_argument("--publish-dashboard", action="store_true")
    args = parser.parse_args()
    if args.trials_per_scenario < 1:
        parser.error("--trials-per-scenario must be positive")
    output = Path(args.output)
    summary = run_research_experiment(output, ResearchConfig(
        trials_per_scenario=args.trials_per_scenario,
        base_seed=args.base_seed,
    ))
    if args.publish_dashboard:
        target = Path("dashboard/public/evaluation/research")
        target.mkdir(parents=True, exist_ok=True)
        for filename in ("summary.json", "trials.json", "trials.csv", "robustness.csv", "per-scenario.csv"):
            shutil.copy2(output / filename, target / filename)
    print(json.dumps({
        "output": str(output), "trial_counts": summary["trial_counts"],
        "confusion_matrix": summary["confusion_matrix"], "metrics": summary["metrics"],
        "held_out": summary["held_out"],
    }, indent=2))
    return 0 if summary["trial_counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
