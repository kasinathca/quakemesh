from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(base_url: str, path: str) -> dict:
    request = urllib.request.Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    if payload.get("schema_version") != "2.0" or not payload.get("request_id"):
        raise RuntimeError(f"{path} did not return a V2 envelope")
    return payload["data"]


def simulator_summary(trace_path: Path | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "trace_available": False,
        "heartbeats": 0,
        "triggers": 0,
        "mqtt_publish_successes": 0,
        "publish_failures": 0,
        "alerts_received": 0,
    }
    if not trace_path or not trace_path.exists():
        return summary
    records = json.loads(trace_path.read_text(encoding="utf-8")).get("records", [])
    summary["trace_available"] = True
    for record in records:
        kind = record.get("kind")
        if kind == "heartbeat":
            summary["heartbeats"] += 1
        elif kind == "trigger":
            summary["triggers"] += 1
        elif kind == "alert_received":
            summary["alerts_received"] += 1
        if kind in {"heartbeat", "trigger"}:
            if record.get("error"):
                summary["publish_failures"] += 1
            elif (record.get("result") or {}).get("published"):
                summary["mqtt_publish_successes"] += 1
    return summary


def classify(observation: dict[str, Any]) -> str:
    if observation.get("scenario_devices", 0) == 0 or observation.get("evidence_count") == 0:
        return "INGRESS_FAILURE"
    if observation.get("evidence_count") is not None and observation.get("confirmed_events", 0) == 0:
        return "CORRELATION_FAILURE"
    if observation.get("confirmed_events", 0) > 0 and observation.get("alerts", 0) == 0:
        return "ALERT_DISPATCH_FAILURE"
    return "WARMUP_VERIFICATION_FAILURE"


def write_diagnostics(directory: Path | None, report: dict[str, Any]) -> None:
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "summary.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (directory / "warmup-observations.json").write_text(
        json.dumps(report.get("observations", []), indent=2, default=str), encoding="utf-8"
    )
    (directory / "simulator-summary.json").write_text(
        json.dumps(report.get("simulator", {}), indent=2, default=str), encoding="utf-8"
    )
    lines = [
        f"session_id: {report.get('session_id')}",
        f"status: {report.get('status')}",
        f"failure_stage: {report.get('failure_stage')}",
        f"reason: {report.get('final_reason')}",
        f"poll_attempts: {report.get('poll_attempts')}",
        f"elapsed_seconds: {report.get('elapsed_seconds')}",
        "capture: API observations and sanitized simulator counters; no credentials or tokens retained",
    ]
    (directory / "diagnostics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def evidence_count(config: dict[str, Any]) -> int | None:
    """Return an authoritative count; callers retain any failure as diagnostics."""
    table_name = (config.get("tables") or {}).get("evidence")
    if not table_name:
        return None
    import boto3

    session = boto3.Session(profile_name=config.get("profile")) if config.get("profile") else boto3.Session()
    table = session.resource("dynamodb", region_name=config.get("region")).Table(table_name)
    count = 0
    kwargs: dict[str, Any] = {"Select": "COUNT", "ConsistentRead": True}
    while True:
        response = table.scan(**kwargs)
        count += int(response.get("Count", 0))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return count
        kwargs["ExclusiveStartKey"] = last_key


def verify(
    config: dict[str, Any],
    minimum_devices: int,
    timeout_seconds: int,
    poll_seconds: float,
    diagnostics_dir: Path | None,
    trace_path: Path | None,
) -> dict[str, Any]:
    started_wall = utc_now()
    started = time.monotonic()
    deadline = started + timeout_seconds
    observations: list[dict[str, Any]] = []
    transient_errors: list[dict[str, Any]] = []
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        attempt = len(observations) + len(transient_errors) + 1
        try:
            devices = read(config["api_base_url"], "/v1/devices?limit=1000").get("items", [])
            events = read(config["api_base_url"], "/v1/events?limit=500").get("items", [])
            alerts = read(config["api_base_url"], "/v1/alerts?limit=2000").get("items", [])
        except (OSError, RuntimeError, ValueError, urllib.error.URLError) as error:
            transient_errors.append({"attempt": attempt, "at": utc_now(), "error": repr(error)})
            time.sleep(poll_seconds)
            continue
        scenario_devices = [
            item for item in devices
            if item.get("provenance_type") == "scenario" and item.get("scenario_run_id") == config["session_id"]
        ]
        scenario_events = [
            item for item in events
            if item.get("provenance_type") == "scenario" and item.get("scenario_run_id") == config["session_id"]
        ]
        confirmed = [
            item for item in scenario_events
            if item.get("status") == "CONFIRMED"
            and len(set(item.get("device_ids", []))) >= minimum_devices
            and len(set(item.get("detection_footprint", []))) >= 3
            and item.get("warning_frontier")
        ]
        event_ids = {item["event_id"] for item in confirmed}
        matching_alerts = [
            item for item in alerts
            if item.get("event_id") in event_ids
            and item.get("provenance_type") == "scenario"
            and item.get("scenario_run_id") == config["session_id"]
        ]
        statuses = {str(item.get("status")) for item in scenario_events}
        evidence_error = None
        try:
            authoritative_evidence_count = evidence_count(config)
        except Exception as error:
            authoritative_evidence_count = None
            evidence_error = repr(error)
        last = {
            "attempt": attempt,
            "observed_at": utc_now(),
            "scenario_devices": len(scenario_devices),
            "evidence_count": authoritative_evidence_count,
            "evidence_count_error": evidence_error,
            "scenario_events": len(scenario_events),
            "confirmed_events": len(confirmed),
            "event_statuses": {status: sum(1 for item in scenario_events if item.get("status") == status) for status in statuses},
            "alerts": len(matching_alerts),
        }
        observations.append(last)
        if len(scenario_devices) >= minimum_devices and confirmed and matching_alerts:
            report = _report("PASS", None, "authoritative scenario device, event, and alert criteria satisfied", config, started_wall, started, attempt, trace_path, observations, transient_errors, last)
            write_diagnostics(diagnostics_dir, report)
            return report
        time.sleep(poll_seconds)
    stage = classify(last)
    report = _report("FAIL", stage, f"authoritative warm-up criteria not reached before {timeout_seconds}s timeout", config, started_wall, started, len(observations) + len(transient_errors), trace_path, observations, transient_errors, last)
    write_diagnostics(diagnostics_dir, report)
    raise RuntimeError(f"{stage}: AWS distributed warm-up did not reach authoritative success: {last}")


def _report(status, stage, reason, config, started_wall, started, attempts, trace_path, observations, errors, last):
    return {
        "schema_version": "1.0", "status": status, "failure_stage": stage, "final_reason": reason,
        "session_id": config["session_id"], "started_at": started_wall, "completed_at": utc_now(),
        "poll_attempts": attempts, "elapsed_seconds": round(time.monotonic() - started, 3),
        "deployment": {key: config.get(key) for key in ("stack_name", "account_id", "region", "expires_at")},
        "simulator": simulator_summary(trace_path), "observations": observations,
        "transient_errors": errors, "final_observation": last,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--minimum-devices", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--diagnostics-dir", type=Path)
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    report = verify(config, args.minimum_devices, args.timeout_seconds, args.poll_seconds, args.diagnostics_dir, args.trace)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
