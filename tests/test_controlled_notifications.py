from __future__ import annotations

import json
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

from aws.lambdas import api


class FakeTable:
    def __init__(self):
        self.items: dict[str, dict] = {}

    def get_item(self, Key, **_kwargs):
        item = self.items.get(Key["alert_id"])
        return {"Item": dict(item)} if item else {}

    def scan(self, **_kwargs):
        return {"Items": []}

    def put_item(self, Item, **_kwargs):
        self.items[Item["alert_id"]] = dict(Item)
        return {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues, **_kwargs):
        item = self.items[Key["alert_id"]]
        if ":published" in ExpressionAttributeValues:
            item.update(status="SNS_ACCEPTED", updated_at_ms=ExpressionAttributeValues[":now"], sns_accepted_at_ms=ExpressionAttributeValues[":now"])
        elif ":state" in ExpressionAttributeValues:
            item.update(status=ExpressionAttributeValues[":state"], updated_at_ms=ExpressionAttributeValues[":now"])
        return {}


class FakeSns:
    def __init__(self):
        self.calls: list[dict] = []

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "sns-1"}


def request_event(api_key_id: str, body: dict) -> dict:
    return {
        "httpMethod": "POST", "path": "/v1/controlled-tests", "headers": {"x-api-key": api_key_id},
        "requestContext": {"requestId": "request-1", "identity": {"apiKeyId": api_key_id}},
        "body": json.dumps(body),
    }


def test_controlled_notification_requires_distinct_operator_key(monkeypatch):
    monkeypatch.setattr(api, "_operator_key", lambda: "operator-key-id")
    response = api.handler(request_event("android-demo-key-id", {"device_id": "d1", "test_message_id": "test-1234"}), None)
    assert response["statusCode"] == 403
    assert json.loads(response["body"])["error"]["code"] == "OPERATOR_AUTHORIZATION_REQUIRED"


def test_controlled_notification_is_session_owned_idempotent_and_hides_endpoint(monkeypatch):
    monkeypatch.setattr(api, "_operator_key", lambda: "operator-key-id")
    monkeypatch.setenv("QM_SESSION_ID", "session-1")
    table = FakeTable()
    sns = FakeSns()
    monkeypatch.setattr(api, "_table", lambda _name: table)
    monkeypatch.setattr(api, "sns", sns)
    monkeypatch.setattr(api, "now_ms", lambda: 1_700_000_000_000)
    monkeypatch.setattr(api, "_find_physical_device", lambda device_id: {
        "device_id": device_id, "session_id": "session-1", "provenance_type": "physical",
        "last_seen_ms": 1_700_000_000_000, "fcm_endpoint_arn": "arn:secret:endpoint",
    })
    event = request_event("operator-key-id", {
        "device_id": "physical-1", "test_message_id": "test-1234",
        "target_arn": "arn:attacker:must-be-ignored",
    })
    first = api.handler(event, None)
    second = api.handler(event, None)
    assert first["statusCode"] == 202
    assert second["statusCode"] == 200
    assert len(sns.calls) == 1
    assert sns.calls[0]["TargetArn"] == "arn:secret:endpoint"
    assert "arn:secret:endpoint" not in first["body"]
    assert json.loads(second["body"])["data"]["idempotent_replay"] is True
