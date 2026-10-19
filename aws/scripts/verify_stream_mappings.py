from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import boto3


INTEGRATIONS = {
    "evidence_to_correlator": {
        "table_logical_prefix": "Evidence",
        "function_logical_prefix": "CorrelatorFn",
        "expected_view_type": "NEW_IMAGE",
    },
    "event_to_dispatcher": {
        "table_logical_prefix": "Events",
        "function_logical_prefix": "DispatcherFn",
        "expected_view_type": "NEW_AND_OLD_IMAGES",
    },
}

TERMINAL_BAD_MAPPING_STATES = {"Disabled", "Failed"}
PENDING_MAPPING_STATES = {"Creating", "Enabling", "Updating", "Disabling"}
BAD_PROCESSING_MARKERS = ("error", "failed", "problem", "permission", "invalid")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stack_resources(cloudformation, stack_name: str) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    token = None
    while True:
        kwargs = {"StackName": stack_name}
        if token:
            kwargs["NextToken"] = token
        response = cloudformation.list_stack_resources(**kwargs)
        resources.extend(response.get("StackResourceSummaries", []))
        token = response.get("NextToken")
        if not token:
            return resources


def _physical_id(resources: list[dict[str, Any]], resource_type: str, prefix: str) -> str:
    matches = [
        item for item in resources
        if item.get("ResourceType") == resource_type
        and str(item.get("LogicalResourceId", "")).startswith(prefix)
        and item.get("PhysicalResourceId")
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {resource_type} resource with logical prefix {prefix}; found {len(matches)}"
        )
    return str(matches[0]["PhysicalResourceId"])


def _event_source_mappings(lambda_client, function_name: str) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    marker = None
    while True:
        kwargs = {"FunctionName": function_name}
        if marker:
            kwargs["Marker"] = marker
        response = lambda_client.list_event_source_mappings(**kwargs)
        mappings.extend(response.get("EventSourceMappings", []))
        marker = response.get("NextMarker")
        if not marker:
            break
    detailed = []
    for mapping in mappings:
        uuid = mapping.get("UUID")
        detailed.append(lambda_client.get_event_source_mapping(UUID=uuid) if uuid else mapping)
    return detailed


def _mapping_summary(mapping: dict[str, Any]) -> dict[str, Any]:
    return {
        key: mapping.get(key)
        for key in (
            "UUID",
            "EventSourceArn",
            "FunctionArn",
            "State",
            "StateTransitionReason",
            "LastProcessingResult",
            "LastModified",
            "StartingPosition",
            "BatchSize",
            "MaximumRetryAttempts",
            "MaximumRecordAgeInSeconds",
            "BisectBatchOnFunctionError",
            "FunctionResponseTypes",
        )
        if mapping.get(key) is not None
    }


def read_snapshot(config: dict[str, Any], profile: str | None = None) -> dict[str, Any]:
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    region = config["region"]
    identity = session.client("sts", region_name=region).get_caller_identity()
    if str(identity["Account"]) != str(config["account_id"]):
        raise RuntimeError("stream-readiness account does not match runtime configuration")
    cloudformation = session.client("cloudformation", region_name=region)
    dynamodb = session.client("dynamodb", region_name=region)
    streams = session.client("dynamodbstreams", region_name=region)
    lambda_client = session.client("lambda", region_name=region)
    resources = _stack_resources(cloudformation, config["stack_name"])
    result: dict[str, Any] = {
        "captured_at": utc_now(),
        "stack_name": config["stack_name"],
        "session_id": config["session_id"],
        "region": region,
        "integrations": {},
    }
    for name, expected in INTEGRATIONS.items():
        table_name = _physical_id(
            resources, "AWS::DynamoDB::Table", expected["table_logical_prefix"]
        )
        function_name = _physical_id(
            resources, "AWS::Lambda::Function", expected["function_logical_prefix"]
        )
        table = dynamodb.describe_table(TableName=table_name)["Table"]
        stream_arn = table.get("LatestStreamArn")
        stream_description = None
        if stream_arn:
            stream_description = streams.describe_stream(StreamArn=stream_arn).get(
                "StreamDescription", {}
            )
        function = lambda_client.get_function(FunctionName=function_name)["Configuration"]
        mappings = _event_source_mappings(lambda_client, function_name)
        matching = [item for item in mappings if item.get("EventSourceArn") == stream_arn]
        result["integrations"][name] = {
            "expected_stream_view_type": expected["expected_view_type"],
            "table": {
                "name": table_name,
                "arn": table.get("TableArn"),
                "stream_enabled": bool((table.get("StreamSpecification") or {}).get("StreamEnabled")),
                "stream_view_type": (table.get("StreamSpecification") or {}).get("StreamViewType"),
                "latest_stream_arn": stream_arn,
                "latest_stream_label": table.get("LatestStreamLabel"),
            },
            "stream": {
                "arn": stream_arn,
                "status": (stream_description or {}).get("StreamStatus"),
                "view_type": (stream_description or {}).get("StreamViewType"),
                "creation_request_date_time": (stream_description or {}).get(
                    "CreationRequestDateTime"
                ),
                "shard_count": len((stream_description or {}).get("Shards", [])),
            },
            "function": {
                "name": function_name,
                "arn": function.get("FunctionArn"),
                "handler": function.get("Handler"),
                "runtime": function.get("Runtime"),
                "state": function.get("State"),
                "state_reason": function.get("StateReason"),
                "last_update_status": function.get("LastUpdateStatus"),
                "last_update_status_reason": function.get("LastUpdateStatusReason"),
                "timeout": function.get("Timeout"),
            },
            "mapping": _mapping_summary(matching[0]) if len(matching) == 1 else None,
            "mapping_match_count": len(matching),
            "all_function_mappings": [_mapping_summary(item) for item in mappings],
        }
    return result


def assess_snapshot(snapshot: dict[str, Any]) -> tuple[bool, bool, list[str]]:
    """Return (ready, fatal, findings) for a stream-integration snapshot."""
    findings: list[str] = []
    fatal = False
    for name, integration in snapshot.get("integrations", {}).items():
        table = integration.get("table") or {}
        stream = integration.get("stream") or {}
        function = integration.get("function") or {}
        mappings = integration.get("all_function_mappings") or []
        mapping = integration.get("mapping")
        expected_view = integration.get("expected_stream_view_type")
        if not table.get("stream_enabled") or not table.get("latest_stream_arn"):
            findings.append(f"{name}: DynamoDB stream is not enabled")
            fatal = True
        if table.get("stream_view_type") != expected_view or stream.get("view_type") != expected_view:
            findings.append(
                f"{name}: stream view type is {table.get('stream_view_type') or stream.get('view_type')}, expected {expected_view}"
            )
            fatal = True
        if stream.get("status") != "ENABLED":
            findings.append(f"{name}: stream status is {stream.get('status') or 'unknown'}")
            fatal = fatal or stream.get("status") in {"DISABLED", "DISABLING"}
        if function.get("state") != "Active" or function.get("last_update_status") != "Successful":
            findings.append(
                f"{name}: function state/update is {function.get('state')}/{function.get('last_update_status')}"
            )
            fatal = fatal or function.get("state") == "Failed" or function.get("last_update_status") == "Failed"
        if integration.get("mapping_match_count") != 1 or not mapping:
            if mappings:
                findings.append(f"{name}: no unique mapping references the expected stream ARN")
                fatal = True
            else:
                findings.append(f"{name}: event-source mapping is not discoverable yet")
            continue
        state = str(mapping.get("State") or "unknown")
        if state != "Enabled":
            findings.append(
                f"{name}: mapping state is {state}; reason={mapping.get('StateTransitionReason') or 'unavailable'}"
            )
            fatal = fatal or state in TERMINAL_BAD_MAPPING_STATES
        result = str(mapping.get("LastProcessingResult") or "")
        if state == "Enabled" and result and any(marker in result.lower() for marker in BAD_PROCESSING_MARKERS):
            findings.append(f"{name}: unhealthy last processing result: {result}")
            fatal = True
    ready = bool(snapshot.get("integrations")) and not findings
    return ready, fatal, findings


def _write_report(directory: Path | None, report: dict[str, Any]) -> None:
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "stream-readiness.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )


def verify(
    config: dict[str, Any],
    timeout_seconds: int,
    poll_seconds: float,
    diagnostics_dir: Path | None,
    profile: str | None = None,
    snapshot_reader: Callable[[], dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    reader = snapshot_reader or (lambda: read_snapshot(config, profile))
    started_at = utc_now()
    started = clock()
    deadline = started + timeout_seconds
    observations: list[dict[str, Any]] = []
    transient_errors: list[dict[str, Any]] = []
    last_findings: list[str] = []
    while True:
        try:
            snapshot = reader()
            ready, fatal, findings = assess_snapshot(snapshot)
            last_findings = findings
            observations.append(snapshot)
            if ready:
                report = {
                    "schema_version": "1.0",
                    "status": "PASS",
                    "session_id": config["session_id"],
                    "started_at": started_at,
                    "completed_at": utc_now(),
                    "elapsed_seconds": round(clock() - started, 3),
                    "attempts": len(observations) + len(transient_errors),
                    "findings": [],
                    "transient_errors": transient_errors,
                    "final_snapshot": snapshot,
                }
                _write_report(diagnostics_dir, report)
                return report
            if fatal:
                break
        except Exception as error:
            transient_errors.append({"at": utc_now(), "error": repr(error)})
        if clock() >= deadline:
            break
        sleeper(poll_seconds)
    report = {
        "schema_version": "1.0",
        "status": "FAIL",
        "failure_stage": "STREAM_READINESS_FAILURE",
        "session_id": config["session_id"],
        "started_at": started_at,
        "completed_at": utc_now(),
        "elapsed_seconds": round(clock() - started, 3),
        "attempts": len(observations) + len(transient_errors),
        "findings": last_findings or ["stream readiness could not be established"],
        "transient_errors": transient_errors,
        "final_snapshot": observations[-1] if observations else None,
        "diagnostic_limitations": [
            "LastProcessingResult can remain empty until the first batch is processed.",
            "CloudWatch metrics can arrive after the readiness decision.",
        ],
    }
    _write_report(diagnostics_dir, report)
    raise RuntimeError(
        "STREAM_READINESS_FAILURE: " + "; ".join(report["findings"])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify QuakeMesh DynamoDB stream integrations")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profile")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--diagnostics-dir", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    report = verify(
        config,
        args.timeout_seconds,
        args.poll_seconds,
        args.diagnostics_dir,
        args.profile,
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
