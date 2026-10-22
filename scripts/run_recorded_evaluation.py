from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.recorded import download_uci_har, evaluate_uci_har


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the production motion gate on recorded UCI HAR smartphone accelerometer windows")
    parser.add_argument("--archive", default="artifacts/datasets/uci-har.zip")
    parser.add_argument("--output", default="results/recorded-negative-evaluation")
    parser.add_argument("--max-windows-per-split", type=int, default=1_000)
    parser.add_argument("--download", action="store_true", help="Explicitly download the 58.2 MB CC BY 4.0 archive when absent")
    args = parser.parse_args()
    archive = Path(args.archive)
    if not archive.exists():
        if not args.download:
            parser.error(f"archive not found: {archive}; pass --download to fetch it explicitly")
        download_uci_har(archive)
    summary = evaluate_uci_har(archive, args.output, args.max_windows_per_split)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
