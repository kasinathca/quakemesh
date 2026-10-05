from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import boto3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_runtime_config(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def validate_trace(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".json":
        raise ValueError("trace must be a .json file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("trace_schema") != "1.0" or not isinstance(data.get("records"), list):
        raise ValueError("not a QuakeMesh trace_schema 1.0 artifact")
    return data


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "uncommitted"


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload one QuakeMesh experiment trace to the retained S3 archive")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--bucket")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--runtime-config", default="artifacts/runtime-config.json")
    parser.add_argument("--prefix", default="traces")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    trace = Path(args.trace).resolve()
    payload = validate_trace(trace)
    config = load_runtime_config(Path(args.runtime_config))
    bucket = args.bucket or config.get("archive_bucket")
    if not bucket:
        parser.error("--bucket is required when archive_bucket is unavailable in runtime config")

    root = Path(__file__).resolve().parents[2]
    checksum = sha256_file(trace)
    now = datetime.now(timezone.utc)
    key = str(PurePosixPath(args.prefix) / now.strftime("%Y/%m/%d") / trace.name)
    metadata = {
        "sha256": checksum,
        "trace-schema": str(payload.get("trace_schema")),
        "git-commit": git_commit(root),
    }

    if args.dry_run:
        print(json.dumps({"bucket": bucket, "key": key, "sha256": checksum, "metadata": metadata}, indent=2))
        return

    s3 = boto3.client("s3", region_name=args.region)
    s3.upload_file(
        str(trace),
        str(bucket),
        key,
        ExtraArgs={
            "ContentType": "application/json",
            "ServerSideEncryption": "AES256",
            "Metadata": metadata,
        },
    )
    print(f"uploaded s3://{bucket}/{key}")
    print(f"sha256 {checksum}")


if __name__ == "__main__":
    main()
