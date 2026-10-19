from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from aws.lambdas import correlator, dispatcher
from aws.scripts import capture_diagnostics, verify_warmup
from quakemesh_core.config import DetectionConfig
from quakemesh_core.correlation import canonicalize_trigger, detect
from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.models import TelemetryTrigger
from simulator.fleet import Fleet


def distributed_evidence(base_ms: int = 1_000_000):
    geo = H3GeoIndex()
    cfg = DetectionConfig()
    evidence = []
    phones = Fleet.around(25, 12.9716, 77.5946)
    for ordinal, phone in enumerate(phones[:8]):
        evidence.append(canonicalize_trigger(TelemetryTrigger(
            "1.0", phone.device_id, 2, base_ms + ordinal * 70,
            phone.latitude, phone.longitude, 1.2, 2.4, "aws-iot",
        ), geo, cfg))
    return evidence


def test_real_distributed_layout_has_valid_connected_h3_diversity():
    evidence = distributed_evidence()
    decision = detect(evidence, max(item.observed_at_ms for item in evidence), H3GeoIndex(), DetectionConfig())
    assert decision.confirmed
    assert len(decision.device_ids) == 8
    assert len(decision.cells) == 4
    assert max(H3GeoIndex().grid_distance(a, b) for a in decision.cells for b in decision.cells) == 3


def test_late_oldest_stream_record_re_evaluates_at_latest_observation(monkeypatch):
    evidence = distributed_evidence()
    oldest = evidence[0]
    # This is the production failure mode: a late stream record can have an
    # observation timestamp older than already committed evidence.
    assert not detect(evidence, oldest.observed_at_ms, H3GeoIndex(), DetectionConfig()).confirmed
    monkeypatch.setattr(correlator, "_window_around", lambda *args: evidence)
    monkeypatch.setattr(correlator, "_geo", H3GeoIndex())
    inserted = {
        "observed_at_ms": oldest.observed_at_ms,
        "provenance_type": "scenario",
        "scenario_run_id": "session-1",
    }
    decision, evaluation_time, provenance, run_id = correlator._evaluate(inserted, DetectionConfig())
    assert decision.confirmed
    assert evaluation_time == max(item.observed_at_ms for item in evidence)
    assert (provenance, run_id) == ("scenario", "session-1")


class PaginatedDeviceTable:
    def __init__(self):
        self.calls = 0

    def scan(self, **kwargs):
        assert kwargs["ConsistentRead"] is True
        self.calls += 1
        if self.calls == 1:
            return {
                "Items": [{"device_id": "d1", "correlation_cell": "wanted"}],
                "LastEvaluatedKey": {"device_key": "one"},
            }
        return {"Items": [{"device_id": "d2", "correlation_cell": "other"}]}


class FakeDdb:
    def __init__(self, table):
        self.table = table

    def Table(self, name):
        assert name == "devices"
        return self.table


def test_dispatch_targets_use_strong_base_table_read_and_paginate(monkeypatch):
    table = PaginatedDeviceTable()
    monkeypatch.setattr(dispatcher, "ddb", FakeDdb(table))
    monkeypatch.setenv("QM_DEVICE_TABLE", "devices")
    found = dispatcher.targets(["wanted"], 100, "scenario", "run-1")
    assert [item["device_id"] for item in found] == ["d1"]
    assert table.calls == 2


def test_failed_verification_preserves_sanitized_diagnostics(tmp_path, monkeypatch):
    config = {
        "session_id": "session-1", "api_base_url": "https://example.invalid",
        "api_key": "must-not-be-written", "region": "ap-south-1", "tables": {},
    }
    trace = tmp_path / "trace.json"
    trace.write_text(json.dumps({"records": [
        {"kind": "heartbeat", "result": {"published": True}, "error": None},
        {"kind": "trigger", "result": {"published": True}, "error": None},
    ]}), encoding="utf-8")

    def fake_read(_base, path):
        if "devices" in path:
            return {"items": [{"provenance_type": "scenario", "scenario_run_id": "session-1"}]}
        return {"items": []}

    monkeypatch.setattr(verify_warmup, "read", fake_read)
    monkeypatch.setattr(verify_warmup, "evidence_count", lambda _config: 0)
    diagnostics = tmp_path / "durable"
    with pytest.raises(RuntimeError, match="INGRESS_FAILURE"):
        verify_warmup.verify(config, 4, 0, 0, diagnostics, trace)
    summary = json.loads((diagnostics / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "FAIL"
    assert summary["failure_stage"] == "INGRESS_FAILURE"
    assert summary["simulator"]["mqtt_publish_successes"] == 2
    assert "must-not-be-written" not in (diagnostics / "summary.json").read_text(encoding="utf-8")


def test_cloud_diagnostic_sanitizer_recurses_without_exposing_tokens():
    value = {"device_id": "d1", "fcm_token": "secret-value", "nested": [{"api_key": "key-value"}]}
    assert capture_diagnostics.sanitized(value) == {
        "device_id": "d1", "fcm_token": "[REDACTED]", "nested": [{"api_key": "[REDACTED]"}],
    }


def test_failure_classification_requires_authoritative_stage_evidence():
    assert verify_warmup.classify({"scenario_devices": 25, "evidence_count": 0}) == "INGRESS_FAILURE"
    assert verify_warmup.classify({"scenario_devices": 25, "evidence_count": 8, "confirmed_events": 0}) == "CORRELATION_FAILURE"
    assert verify_warmup.classify({"scenario_devices": 25, "evidence_count": None, "confirmed_events": 0}) == "WARMUP_VERIFICATION_FAILURE"
    assert verify_warmup.classify({"scenario_devices": 25, "evidence_count": 8, "confirmed_events": 1, "alerts": 0}) == "ALERT_DISPATCH_FAILURE"
