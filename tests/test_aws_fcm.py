from __future__ import annotations

import json
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from aws.lambdas import api, dispatcher


class FakeSns:
    def __init__(self):
        self.published: dict | None = None

    def publish(self, **kwargs):
        self.published = kwargs
        return {"MessageId": "message-1"}


def test_fcm_v1_delivery_is_data_only_and_alert_id_first(monkeypatch):
    sns = FakeSns()
    monkeypatch.setattr(dispatcher, "sns", sns)

    dispatcher.send_fcm(
        "arn:aws:sns:ap-south-1:123456789012:endpoint/GCM/quakemesh/device-1",
        {"event_id": "event-9", "version": 3, "status": "CONFIRMED"},
        "event-9:device-2",
        "device-2",
        1_700_000_000_000,
    )

    assert sns.published is not None
    assert sns.published["MessageStructure"] == "json"
    outer = json.loads(sns.published["Message"])
    fcm = json.loads(outer["GCM"])["fcmV1Message"]["message"]
    assert "notification" not in fcm
    assert fcm["android"] == {"priority": "high"}
    assert fcm["data"] == {
        "type": "QUAKEMESH_WARNING",
        "alert_id": "event-9:device-2",
        "event_id": "event-9",
        "event_version": "3",
        "status": "CONFIRMED",
        "device_id": "device-2",
        "created_at_ms": "1700000000000",
    }


def test_controlled_fcm_payload_is_non_authoritative_and_explicitly_labeled(monkeypatch):
    monkeypatch.setenv("QM_SESSION_ID", "session-1")
    outer = json.loads(api._controlled_payload("test-msg-123", "physical-1", 1_700_000_000_000))
    message = json.loads(outer["GCM"])["fcmV1Message"]["message"]
    assert "notification" not in message
    assert message["data"]["type"] == "QUAKEMESH_CONTROLLED_TEST"
    assert message["data"]["controlled_test"] == "true"
    assert message["data"]["authoritative_record"] == "false"
    assert message["data"]["event_id"] == "CONTROLLED-TEST"
    assert message["data"]["title"] == "CONTROLLED TEST — NOT AN EARTHQUAKE ALERT"
    assert "TargetArn" not in message["data"]
