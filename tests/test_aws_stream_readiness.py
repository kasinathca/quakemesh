from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime, timezone
import os
from pathlib import Path

import pytest
from boto3.dynamodb.types import TypeSerializer

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from aws.lambdas import correlator, dispatcher
from aws.scripts import capture_diagnostics, verify_stream_mappings
from quakemesh_core.config import DetectionConfig
from quakemesh_core.correlation import detect
from quakemesh_core.geo import H3GeoIndex
from tests.test_aws_pipeline_reliability import distributed_evidence


EXPECTED_EVIDENCE_STREAM = "arn:aws:dynamodb:ap-south-1:123456789012:table/evidence/stream/new"


def integration_snapshot(
    state: str = "Enabled",
    event_source_arn: str = EXPECTED_EVIDENCE_STREAM,
    processing_result: str = "No records processed",
) -> dict:
    def integration(name: str, expected_arn: str, view: str) -> dict:
        mapping = {
            "UUID": f"uuid-{name}",
            "EventSourceArn": event_source_arn if name == "evidence_to_correlator" else expected_arn,
            "State": state,
            "StateTransitionReason": "User action" if state == "Disabled" else "",
            "LastProcessingResult": processing_result,
            "StartingPosition": "TRIM_HORIZON",
        }
        return {
            "expected_stream_view_type": view,
            "table": {
                "stream_enabled": True,
                "stream_view_type": view,
                "latest_stream_arn": expected_arn,
            },
            "stream": {"status": "ENABLED", "view_type": view, "arn": expected_arn},
            "function": {"state": "Active", "last_update_status": "Successful"},
            "mapping": mapping if mapping["EventSourceArn"] == expected_arn else None,
            "mapping_match_count": int(mapping["EventSourceArn"] == expected_arn),
            "all_function_mappings": [mapping],
        }

    event_arn = "arn:aws:dynamodb:ap-south-1:123456789012:table/events/stream/new"
    return {
        "integrations": {
            "evidence_to_correlator": integration(
                "evidence_to_correlator", EXPECTED_EVIDENCE_STREAM, "NEW_IMAGE"
            ),
            "event_to_dispatcher": integration(
                "event_to_dispatcher", event_arn, "NEW_AND_OLD_IMAGES"
            ),
        }
    }


def test_latest_can_miss_pre_activation_records_but_trim_horizon_replays_them():
    records = [(1, "before-a"), (2, "before-b"), (3, "after")]
    activation_sequence = 2
    latest_visible = [value for sequence, value in records if sequence > activation_sequence]
    trim_horizon_visible = [value for _sequence, value in records]
    assert latest_visible == ["after"]
    assert trim_horizon_visible == ["before-a", "before-b", "after"]
    stack = Path("aws/infrastructure/stack.py").read_text(encoding="utf-8")
    assert stack.count("StartingPosition.TRIM_HORIZON") == 2
    assert "StartingPosition.LATEST" not in stack


def test_mapping_activation_delay_reaches_enabled_and_persists_report(tmp_path):
    snapshots = [integration_snapshot("Creating"), integration_snapshot("Enabling"), integration_snapshot()]
    now = [0.0]

    def reader():
        return snapshots.pop(0)

    def sleep(seconds: float):
        now[0] += seconds

    report = verify_stream_mappings.verify(
        {"session_id": "session-1"}, 10, 1, tmp_path, snapshot_reader=reader,
        clock=lambda: now[0], sleeper=sleep,
    )
    assert report["status"] == "PASS"
    assert report["attempts"] == 3
    assert json.loads((tmp_path / "stream-readiness.json").read_text())["status"] == "PASS"


def test_disabled_mapping_fails_immediately_with_reason(tmp_path):
    with pytest.raises(RuntimeError, match="STREAM_READINESS_FAILURE.*Disabled"):
        verify_stream_mappings.verify(
            {"session_id": "session-1"}, 30, 1, tmp_path,
            snapshot_reader=lambda: integration_snapshot("Disabled"),
        )
    report = json.loads((tmp_path / "stream-readiness.json").read_text())
    assert report["status"] == "FAIL"
    assert "User action" in " ".join(report["findings"])


def test_incorrect_stream_arn_is_fatal():
    ready, fatal, findings = verify_stream_mappings.assess_snapshot(
        integration_snapshot(event_source_arn="arn:aws:dynamodb:wrong")
    )
    assert not ready and fatal
    assert any("expected stream ARN" in finding for finding in findings)


def test_readiness_timeout_preserves_diagnostics(tmp_path):
    now = [0.0]

    def sleep(seconds: float):
        now[0] += seconds

    with pytest.raises(RuntimeError, match="STREAM_READINESS_FAILURE"):
        verify_stream_mappings.verify(
            {"session_id": "session-1"}, 2, 1, tmp_path,
            snapshot_reader=lambda: integration_snapshot("Creating"),
            clock=lambda: now[0], sleeper=sleep,
        )
    report = json.loads((tmp_path / "stream-readiness.json").read_text())
    assert report["status"] == "FAIL"
    assert report["failure_stage"] == "STREAM_READINESS_FAILURE"


def _stream_record(item: dict, event_name: str = "INSERT") -> dict:
    serializer = TypeSerializer()
    return {
        "eventName": event_name,
        "dynamodb": {"NewImage": {key: serializer.serialize(value) for key, value in item.items()}},
    }


def test_correlator_consumes_insert_and_duplicate_delivery_is_idempotent(monkeypatch):
    evidence = distributed_evidence()
    decision = detect(
        evidence,
        max(item.observed_at_ms for item in evidence),
        H3GeoIndex(),
        DetectionConfig(),
    )
    assert decision.confirmed
    stored = []
    monkeypatch.setattr(
        correlator,
        "_evaluate",
        lambda _item, _cfg: (decision, decision.last_observed_at_ms, "scenario", "session-1"),
    )
    monkeypatch.setattr(correlator, "_active", lambda *_args: list(stored))

    def save(event, old_version):
        if old_version is None:
            stored.append(event)
        return True

    monkeypatch.setattr(correlator, "_save", save)
    monkeypatch.setattr(correlator, "_geo", H3GeoIndex())
    monkeypatch.setenv("QM_SESSION_ID", "session-1")
    item = {
        "evidence_id": "device-1:2", "device_id": "device-1", "seq": 2,
        "observed_at_ms": 1_000_000, "h3_cell": evidence[0].h3_cell,
        "correlation_cell": evidence[0].correlation_cell, "motion_rms": Decimal("1.2"),
        "motion_peak": Decimal("2.4"), "transport": "aws-iot", "provenance_type": "scenario",
        "scenario_run_id": "session-1",
    }
    result = correlator.handler({"Records": [_stream_record(item), _stream_record(item)]}, None)
    assert len(stored) == 1
    assert len(result["changed_events"]) == 1
    assert stored[0].version == 1


def test_correlator_exception_retries_whole_batch(monkeypatch):
    monkeypatch.setattr(
        correlator,
        "_evaluate",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("transient read failure")),
    )
    monkeypatch.setenv("QM_SESSION_ID", "session-1")
    with pytest.raises(RuntimeError, match="transient read failure"):
        correlator.handler(
            {"Records": [_stream_record({"observed_at_ms": 1, "provenance_type": "scenario"})]},
            None,
        )


def test_dispatcher_eventually_publishes_alert_for_confirmed_event(monkeypatch):
    published = []
    marks = []

    class IoTData:
        def publish(self, **kwargs):
            published.append(kwargs)

    monkeypatch.setattr(dispatcher, "targets", lambda *_args: [{"device_id": "device-1", "transport": "aws-iot"}])
    monkeypatch.setattr(dispatcher, "claim_delivery", lambda *_args: True)
    monkeypatch.setattr(dispatcher, "mark", lambda *args: marks.append(args))
    monkeypatch.setattr(dispatcher, "iot_data", lambda: IoTData())
    monkeypatch.setattr(dispatcher, "demo_recipients", lambda *_args: [])
    monkeypatch.setenv("QM_SESSION_ID", "session-1")
    event = {
        "event_id": "scenario#session-1#event-1", "version": 1, "status": "CONFIRMED",
        "updated_at_ms": 1_000_000, "detection_footprint": ["cell-1"],
        "warning_frontier": ["cell-2"], "provenance_type": "scenario",
        "scenario_run_id": "session-1",
    }
    result = dispatcher.handler({"Records": [_stream_record(event)]}, None)
    assert result == {"sent": ["device-1"]}
    assert len(published) == 1
    assert marks[-1][1] == "SENT"


def test_diagnostic_metrics_make_unavailable_data_explicit():
    class CloudWatch:
        def get_metric_statistics(self, **_kwargs):
            return {"Datapoints": []}

    metrics = capture_diagnostics.function_metrics(
        CloudWatch(), ["correlator"], datetime.now(timezone.utc), datetime.now(timezone.utc)
    )
    assert metrics["correlator"]["Invocations"]["status"] == "UNAVAILABLE_OR_NOT_YET_PUBLISHED"
    assert metrics["correlator"]["IteratorAge"]["value"] is None


def test_diagnostic_stdout_serializes_aws_datetime_values():
    rendered = capture_diagnostics.json_document(
        {"mapping": {"LastModified": datetime(2026, 10, 19, tzinfo=timezone.utc)}}
    )

    assert json.loads(rendered)["mapping"]["LastModified"] == "2026-10-19 00:00:00+00:00"
