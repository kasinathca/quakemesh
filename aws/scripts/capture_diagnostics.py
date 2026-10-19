from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3

try:
    from aws.scripts.verify_stream_mappings import assess_snapshot, read_snapshot
except ModuleNotFoundError:  # Direct script execution places aws/scripts first on sys.path.
    from verify_stream_mappings import assess_snapshot, read_snapshot

SENSITIVE_FRAGMENTS = ("api_key", "authorization", "credential", "private", "secret", "token")


def json_document(value: Any) -> str:
    """Serialize boto3 diagnostic values, including AWS datetime fields."""
    return json.dumps(value, indent=2, default=str)


def sanitized(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("[REDACTED]" if any(part in str(key).lower() for part in SENSITIVE_FRAGMENTS) else sanitized(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    return value


def scan_count(table) -> int:
    count = 0
    kwargs: dict[str, Any] = {"Select": "COUNT", "ConsistentRead": True}
    while True:
        response = table.scan(**kwargs)
        count += int(response.get("Count", 0))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return count
        kwargs["ExclusiveStartKey"] = last_key


def lambda_names(cloudformation, stack_name: str) -> list[str]:
    names = []
    token = None
    while True:
        kwargs = {"StackName": stack_name}
        if token:
            kwargs["NextToken"] = token
        response = cloudformation.list_stack_resources(**kwargs)
        names.extend(
            item["PhysicalResourceId"] for item in response.get("StackResourceSummaries", [])
            if item.get("ResourceType") == "AWS::Lambda::Function" and item.get("PhysicalResourceId")
        )
        token = response.get("NextToken")
        if not token:
            return names


def session_logs(logs, names: list[str], session_id: str, start_ms: int) -> tuple[list[dict], list[dict]]:
    timeline = []
    errors = []
    for function_name in names:
        token = None
        while True:
            kwargs: dict[str, Any] = {"logGroupName": f"/aws/lambda/{function_name}", "startTime": start_ms}
            if token:
                kwargs["nextToken"] = token
            try:
                response = logs.filter_log_events(**kwargs)
            except Exception as error:
                errors.append({"function": function_name, "capture_error": repr(error)})
                break
            for entry in response.get("events", []):
                message = str(entry.get("message", "")).strip()
                try:
                    payload = json.loads(message)
                except (TypeError, json.JSONDecodeError):
                    if any(marker in message for marker in (
                        "ERROR", "Task timed out", "Traceback", "Runtime.ImportModuleError", "Unhandled"
                    )):
                        errors.append({"function": function_name, "timestamp": entry.get("timestamp"), "message": message[:1000]})
                    continue
                if payload.get("session_id") != session_id:
                    continue
                row = {"function": function_name, "timestamp": entry.get("timestamp"), **sanitized(payload)}
                timeline.append(row)
                if payload.get("level") == "ERROR" or payload.get("error_type"):
                    errors.append(row)
            next_token = response.get("nextToken")
            if not next_token or next_token == token:
                break
            token = next_token
    timeline.sort(key=lambda item: int(item.get("timestamp") or 0))
    return timeline, errors


def function_metrics(cloudwatch, function_names: list[str], start: datetime, end: datetime) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for function_name in function_names:
        metrics: dict[str, Any] = {}
        for metric_name, statistic in (
            ("Invocations", "Sum"),
            ("Errors", "Sum"),
            ("Throttles", "Sum"),
            ("IteratorAge", "Maximum"),
        ):
            response = cloudwatch.get_metric_statistics(
                Namespace="AWS/Lambda",
                MetricName=metric_name,
                Dimensions=[{"Name": "FunctionName", "Value": function_name}],
                StartTime=start,
                EndTime=end,
                Period=60,
                Statistics=[statistic],
            )
            points = response.get("Datapoints", [])
            metrics[metric_name] = {
                "status": "AVAILABLE" if points else "UNAVAILABLE_OR_NOT_YET_PUBLISHED",
                "statistic": statistic,
                "datapoint_count": len(points),
                "value": (
                    sum(float(point.get(statistic, 0)) for point in points)
                    if statistic == "Sum" and points
                    else max((float(point.get(statistic, 0)) for point in points), default=None)
                ),
                "unit": points[0].get("Unit") if points else None,
            }
        result[function_name] = metrics
    return result


def capture(config: dict[str, Any], output: Path, profile: str | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": "1.0", "session_id": config["session_id"],
        "captured_at": datetime.now(timezone.utc).isoformat(), "status": "PARTIAL", "capture_errors": [],
        "diagnostic_limitations": [
            "CloudWatch metrics can be delayed and an empty datapoint set does not prove zero invocations.",
            "A missing Lambda log group or empty log window does not prove that a function was never invoked.",
            "DynamoDB table counts prove persistence but do not retain payload bodies in this sanitized report.",
            "Deleted event-source mappings cannot be reconstructed after teardown without prior capture or audit history.",
        ],
    }
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    sts = session.client("sts", region_name=config["region"])
    identity = sts.get_caller_identity()
    if str(identity["Account"]) != str(config["account_id"]):
        raise RuntimeError("diagnostic capture account does not match runtime configuration")
    ddb = session.resource("dynamodb", region_name=config["region"])
    counts = {}
    for logical, name in (config.get("tables") or {}).items():
        try:
            counts[logical] = scan_count(ddb.Table(name))
        except Exception as error:
            report["capture_errors"].append({"source": f"dynamodb:{logical}", "error": repr(error)})
    report["table_counts"] = counts
    stream_snapshot = None
    try:
        stream_snapshot = read_snapshot(config, profile)
        ready, fatal, findings = assess_snapshot(stream_snapshot)
        report["stream_integrations"] = {
            "ready": ready,
            "fatal": fatal,
            "findings": findings,
            "snapshot": stream_snapshot,
        }
        (output / "stream-integrations.json").write_text(
            json.dumps(report["stream_integrations"], indent=2, default=str), encoding="utf-8"
        )
    except Exception as error:
        report["capture_errors"].append({"source": "stream_integrations", "error": repr(error)})

    timeline: list[dict] = []
    aws_errors: list[dict] = []
    names: list[str] = []
    created = datetime.fromisoformat(str(config["created_at"]).replace("Z", "+00:00"))
    try:
        cloudformation = session.client("cloudformation", region_name=config["region"])
        logs = session.client("logs", region_name=config["region"])
        names = lambda_names(cloudformation, config["stack_name"])
        timeline, aws_errors = session_logs(logs, names, config["session_id"], int(created.timestamp() * 1000))
        report["cloudwatch_log_capture"] = {
            "function_names": names,
            "start_time": created.isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "structured_session_rows": len(timeline),
            "error_rows": len(aws_errors),
        }
    except Exception as error:
        report["capture_errors"].append({"source": "cloudwatch", "error": repr(error)})
    try:
        metrics = function_metrics(
            session.client("cloudwatch", region_name=config["region"]),
            names,
            created,
            datetime.now(timezone.utc),
        )
        report["lambda_metrics"] = metrics
        (output / "lambda-metrics.json").write_text(
            json.dumps(metrics, indent=2, default=str), encoding="utf-8"
        )
    except Exception as error:
        report["capture_errors"].append({"source": "cloudwatch_metrics", "error": repr(error)})
    stages = Counter(str(item.get("pipeline_stage")) for item in timeline if item.get("pipeline_stage"))
    reasons = Counter(str(item.get("rejection_reason") or item.get("reason")) for item in timeline if item.get("rejection_reason") or item.get("reason"))
    report["log_stage_counts"] = dict(stages)
    report["correlation_rejection_reasons"] = dict(reasons)
    report["status"] = "COMPLETE" if not report["capture_errors"] else "PARTIAL"
    (output / "pipeline-timeline.json").write_text(json.dumps(timeline, indent=2, default=str), encoding="utf-8")
    (output / "aws-errors.json").write_text(json.dumps(aws_errors + report["capture_errors"], indent=2, default=str), encoding="utf-8")
    (output / "correlation-diagnostics.json").write_text(json.dumps({"stage_counts": dict(stages), "rejection_reasons": dict(reasons)}, indent=2), encoding="utf-8")
    (output / "capture-summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture sanitized QuakeMesh diagnostics before teardown")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    print(json_document(capture(config, args.output, args.profile)))


if __name__ == "__main__":
    main()
