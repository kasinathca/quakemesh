from __future__ import annotations

import json
import hmac
import os
import re
from decimal import Decimal

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

from .common import boto3, env, failure, log, now_ms, request_id, success
from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.validation import ValidationError

from .ingress import process

_geo = None
_operator_credential = None
sns = boto3.client("sns")
secretsmanager = boto3.client("secretsmanager")
CONTROLLED_TEST_LABEL = "CONTROLLED TEST — NOT AN EARTHQUAKE ALERT"
_TEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$")


def _geo_index():
    global _geo
    if _geo is None:
        _geo = H3GeoIndex()
    return _geo


def _clean(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    return value


def _event_view(row):
    row = _clean(row)
    geo = _geo_index()
    row["footprint_polygons"] = [
        {"cell": cell, "boundary": geo.boundary(cell)}
        for cell in row.get("detection_footprint", [])
    ]
    row["frontier_polygons"] = [
        {"cell": cell, "boundary": geo.boundary(cell)}
        for cell in row.get("warning_frontier", [])
    ]
    return row


def _table(name: str):
    return boto3.resource("dynamodb").Table(env(name))


def _items(table_name: str, limit: int) -> list[dict]:
    table=_table(table_name);items=[];kwargs={"Limit":limit}
    while len(items)<limit:
        response=table.scan(**kwargs)
        items.extend(response.get("Items",[]))
        last_key=response.get("LastEvaluatedKey")
        if not last_key:break
        kwargs["ExclusiveStartKey"]=last_key
        kwargs["Limit"]=limit-len(items)
    return items[:limit]


def _operator_key() -> str:
    global _operator_credential
    if _operator_credential is None:
        response = secretsmanager.get_secret_value(SecretId=env("QM_OPERATOR_SECRET_ARN"))
        _operator_credential = str(response["SecretString"])
    return _operator_credential


def _is_operator(event: dict) -> bool:
    supplied = _header(event, "x-api-key") or ""
    return bool(supplied and hmac.compare_digest(supplied, _operator_key()))


def _find_physical_device(device_id: str) -> dict | None:
    table = _table("QM_DEVICE_TABLE")
    kwargs = {
        "ConsistentRead": True,
        "FilterExpression": Attr("device_id").eq(device_id) & Attr("provenance_type").eq("physical"),
    }
    while True:
        response = table.scan(**kwargs)
        for row in response.get("Items", []):
            if row.get("session_id") == env("QM_SESSION_ID"):
                return row
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return None
        kwargs["ExclusiveStartKey"] = last_key


def _controlled_view(row: dict) -> dict:
    clean = _clean(row)
    for key in ("fcm_endpoint_arn", "sns_message_id"):
        clean.pop(key, None)
    return clean


def _controlled_payload(test_message_id: str, device_id: str, requested_at_ms: int) -> str:
    data = {
        "type": "QUAKEMESH_CONTROLLED_TEST",
        "controlled_test": "true",
        "authoritative_record": "false",
        "test_message_id": test_message_id,
        "alert_id": f"controlled:{env('QM_SESSION_ID')}:{test_message_id}",
        "event_id": "CONTROLLED-TEST",
        "event_version": "1",
        "status": "CONTROLLED_TEST",
        "device_id": device_id,
        "created_at_ms": str(requested_at_ms),
        "provenance_type": "controlled-test",
        "title": CONTROLLED_TEST_LABEL,
        "body": "Operator-initiated delivery check. This message is not an earthquake warning.",
    }
    inner = {"fcmV1Message": {"message": {"data": data, "android": {"priority": "high"}}}}
    return json.dumps({"GCM": json.dumps(inner), "default": CONTROLLED_TEST_LABEL})


def _request_controlled_test(event: dict, request: str) -> dict:
    if not _is_operator(event):
        return failure(request, 403, "OPERATOR_AUTHORIZATION_REQUIRED", "A session operator credential is required.")
    payload = json.loads(event.get("body") or "{}")
    device_id = payload.get("device_id")
    test_message_id = payload.get("test_message_id")
    if not isinstance(device_id, str) or not device_id or len(device_id) > 128:
        raise ValidationError("device_id is required and must be at most 128 characters")
    if not isinstance(test_message_id, str) or not _TEST_ID.fullmatch(test_message_id):
        raise ValidationError("test_message_id must be 8-80 URL-safe characters")
    device = _find_physical_device(device_id)
    if not device:
        return failure(request, 404, "DEVICE_NOT_ELIGIBLE", "The physical device is not registered in this session.")
    now = now_ms()
    if now - int(device.get("last_seen_ms", 0)) > 120_000:
        return failure(request, 409, "DEVICE_OFFLINE", "The selected device has not reported within 120 seconds.")
    endpoint = device.get("fcm_endpoint_arn")
    if not endpoint:
        return failure(request, 409, "DEVICE_NOT_NOTIFICATION_CAPABLE", "The selected device has no registered FCM endpoint.")

    table = _table("QM_ALERT_TABLE")
    alert_id = f"controlled:{env('QM_SESSION_ID')}:{test_message_id}"
    existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True).get("Item")
    if existing:
        if existing.get("device_id") != device_id:
            return failure(request, 409, "IDEMPOTENCY_CONFLICT", "The test_message_id is already bound to another device.")
        return success(request, {"test": _controlled_view(existing), "idempotent_replay": True})

    recent = table.scan(
        ConsistentRead=True,
        FilterExpression=(Attr("controlled_test").eq(True) & Attr("device_id").eq(device_id) & Attr("requested_at_ms").gte(now - 30_000)),
    ).get("Items", [])
    if recent:
        return failure(request, 429, "CONTROLLED_TEST_RATE_LIMITED", "Wait 30 seconds before sending another test to this device.")
    record = {
        "alert_id": alert_id,
        "event_id": "CONTROLLED-TEST",
        "event_version": 1,
        "device_id": device_id,
        "created_at_ms": now,
        "updated_at_ms": now,
        "requested_at_ms": now,
        "status": "REQUESTED",
        "controlled_test": True,
        "authoritative_record": False,
        "test_message_id": test_message_id,
        "provenance_type": "controlled-test",
        "session_id": env("QM_SESSION_ID"),
        "message_label": CONTROLLED_TEST_LABEL,
        "transport": "sns-fcm",
    }
    try:
        table.put_item(Item=record, ConditionExpression="attribute_not_exists(alert_id)")
        publish = sns.publish(TargetArn=str(endpoint), Message=_controlled_payload(test_message_id, device_id, now), MessageStructure="json")
        published_at = now_ms()
        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET #status=:published,updated_at_ms=:now,sns_accepted_at_ms=:now,sns_message_id=:message",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":published": "SNS_ACCEPTED", ":now": published_at, ":message": str(publish.get("MessageId", ""))},
        )
        record.update({"status": "SNS_ACCEPTED", "updated_at_ms": published_at, "sns_accepted_at_ms": published_at})
    except ClientError as error:
        failed_at = now_ms()
        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET #status=:failed,updated_at_ms=:now,failed_at_ms=:now,failure_detail=:detail",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":failed": "FAILED", ":now": failed_at, ":detail": type(error).__name__},
        )
        raise
    log("CONTROLLED_TEST_PUBLISHED", request, device_id=device_id, test_message_id=test_message_id, alert_id=alert_id)
    return success(request, {"test": _controlled_view(record), "idempotent_replay": False}, 202)


def _controlled_receipt(event: dict, request: str) -> dict:
    test_message_id = str((event.get("pathParameters") or {}).get("test_message_id") or "")
    if not _TEST_ID.fullmatch(test_message_id):
        raise ValidationError("invalid test_message_id")
    payload = json.loads(event.get("body") or "{}")
    device_id = payload.get("device_id")
    state = payload.get("state")
    if not isinstance(device_id, str) or not device_id:
        raise ValidationError("device_id is required")
    ranks = {"FCM_RECEIVED": 1, "NOTIFICATION_POSTED": 2, "OPENED": 3, "FAILED": 4}
    if state not in ranks:
        raise ValidationError("state must be FCM_RECEIVED, NOTIFICATION_POSTED, OPENED, or FAILED")
    alert_id = f"controlled:{env('QM_SESSION_ID')}:{test_message_id}"
    table = _table("QM_ALERT_TABLE")
    existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True).get("Item")
    if not existing or not existing.get("controlled_test"):
        return failure(request, 404, "CONTROLLED_TEST_NOT_FOUND", "The controlled test does not exist in this session.")
    if existing.get("session_id") != env("QM_SESSION_ID") or existing.get("device_id") != device_id:
        return failure(request, 409, "CONTROLLED_TEST_DEVICE_MISMATCH", "The receipt does not belong to this device and session.")
    timestamp = now_ms()
    timestamp_field = {
        "FCM_RECEIVED": "fcm_received_at_ms", "NOTIFICATION_POSTED": "notification_posted_at_ms",
        "OPENED": "opened_at_ms", "FAILED": "failed_at_ms",
    }[state]
    existing_rank = ranks.get(str(existing.get("status")), 0)
    if ranks[state] >= existing_rank:
        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression=f"SET #status=:state,updated_at_ms=:now,{timestamp_field}=:now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":state": state, ":now": timestamp},
        )
        existing.update({"status": state, "updated_at_ms": timestamp, timestamp_field: timestamp})
    log("CONTROLLED_TEST_RECEIPT", request, device_id=device_id, test_message_id=test_message_id, state=state)
    return success(request, {"test": _controlled_view(existing), "transition_observed": ranks[state] >= existing_rank})


def _bounded_limit(event: dict, default: int, maximum: int) -> int:
    raw = (event.get("queryStringParameters") or {}).get("limit")
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as error:
        raise ValidationError("limit must be an integer") from error
    if value < 1 or value > maximum:
        raise ValidationError(f"limit must be between 1 and {maximum}")
    return value


def _header(event: dict, name: str) -> str | None:
    expected = name.lower()
    return next(
        (str(value) for key, value in (event.get("headers") or {}).items() if key.lower() == expected),
        None,
    )


def _physical_ingress(event: dict, path: str, request: str) -> dict:
    if _header(event, "X-QuakeMesh-Run-Id"):
        return failure(
            request,
            409,
            "SCENARIO_INGRESS_NOT_SUPPORTED",
            "The current AWS V2 slice accepts physical HTTPS observations only.",
        )
    body = json.loads(event.get("body") or "{}")
    kind = "heartbeat" if path.endswith("heartbeat") else "trigger"
    device_id = str(body.get("device_id", "")) or None
    log("API_INGRESS_RECEIVED", request, device_id=device_id, observation_kind=kind)
    result = process(body, kind, None, "aws-https", request=request)
    log(
        "DYNAMODB_WRITE_COMPLETED",
        request,
        device_id=device_id,
        observation_kind=kind,
        accepted=result.get("accepted"),
        event_id=result.get("event_id"),
    )
    return success(request, result)


def _acknowledge(event: dict, request: str) -> dict:
    alert_id = str((event.get("pathParameters") or {}).get("alert_id") or "")
    if not alert_id:
        return failure(request, 404, "ALERT_NOT_FOUND", "The requested alert was not found.")
    payload = json.loads(event.get("body") or "{}")
    source = payload.get("acknowledgement_source")
    if source not in {"android", "dashboard"}:
        raise ValidationError("acknowledgement_source must be android or dashboard")
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        raise ValidationError("device_id is required")
    table = _table("QM_ALERT_TABLE")
    existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True).get("Item")
    if not existing:
        return failure(request, 404, "ALERT_NOT_FOUND", "The requested alert was not found.")
    if str(existing.get("device_id")) != device_id:
        return failure(
            request,
            409,
            "ALERT_DEVICE_MISMATCH",
            "The alert is assigned to a different device.",
        )
    changed = existing.get("acknowledged_at_ms") is None
    if changed:
        timestamp = now_ms()
        try:
            table.update_item(
                Key={"alert_id": alert_id},
                UpdateExpression=(
                    "SET #status=:ack,acknowledged_at_ms=:now,"
                    "acknowledgement_source=:source,updated_at_ms=:now"
                ),
                ConditionExpression="attribute_not_exists(acknowledged_at_ms)",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={
                    ":ack": "ACKNOWLEDGED",
                    ":now": timestamp,
                    ":source": source,
                },
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            changed = False
        existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True)["Item"]
    log(
        "ALERT_ACKNOWLEDGED",
        request,
        alert_id=alert_id,
        event_id=existing.get("event_id"),
        device_id=device_id,
        transition_created=changed,
    )
    return success(request, {"alert": _clean(existing), "transition_created": changed})


def handler(event, context):
    request = request_id(event, context)
    method = str(event.get("httpMethod", ""))
    path = str(event.get("path", ""))
    log("API_REQUEST_RECEIVED", request, method=method, path=path)
    try:
        if method == "GET" and path == "/health":
            return success(
                request,
                {
                    "status": "ok",
                    "mode": "AWS",
                    "application_version": "2.0.0",
                    "session_id": env("QM_SESSION_ID"),
                    "region": os.getenv("AWS_REGION", "unknown"),
                    "expires_at": env("QM_EXPIRES_AT"),
                },
            )
        if method == "POST" and path in {
            "/v1/devices/heartbeat",
            "/v1/evidence/trigger",
        }:
            return _physical_ingress(event, path, request)
        if method == "GET" and path == "/v1/devices":
            rows = _items("QM_DEVICE_TABLE", _bounded_limit(event, 200, 1000))
            current = now_ms()
            for row in rows:
                row["online"] = current - int(row.get("last_seen_ms", 0)) <= 120_000
                row["notification_capable"] = bool(row.get("fcm_endpoint_arn"))
                row.pop("fcm_endpoint_arn", None)
            rows.sort(key=lambda item: int(item.get("last_seen_ms", 0)), reverse=True)
            return success(request, {"items": _clean(rows)})
        if method == "GET" and path == "/v1/events":
            rows = _items("QM_EVENT_TABLE", _bounded_limit(event, 100, 500))
            rows.sort(key=lambda item: int(item.get("updated_at_ms", 0)), reverse=True)
            return success(request, {"items": [_event_view(item) for item in rows]})
        if method == "GET" and path == "/v1/alerts":
            rows = _items("QM_ALERT_TABLE", _bounded_limit(event, 200, 2000))
            rows.sort(key=lambda item: int(item.get("created_at_ms", 0)), reverse=True)
            return success(request, {"items": _clean(rows)})
        if method == "POST" and path.startswith("/v1/alerts/") and path.endswith("/ack"):
            return _acknowledge(event, request)
        if method == "POST" and path == "/v1/controlled-tests":
            return _request_controlled_test(event, request)
        if method == "POST" and path.startswith("/v1/controlled-tests/") and path.endswith("/receipts"):
            return _controlled_receipt(event, request)
        return failure(request, 404, "ROUTE_NOT_FOUND", "The requested route was not found.")
    except json.JSONDecodeError:
        return failure(request, 400, "REQUEST_VALIDATION_FAILED", "Request body must be valid JSON.")
    except ValidationError as error:
        return failure(request, 422, "REQUEST_VALIDATION_FAILED", str(error))
    except ValueError as error:
        return failure(request, 422, "REQUEST_VALIDATION_FAILED", str(error))
    except Exception as error:
        log(
            "API_REQUEST_FAILED",
            request,
            method=method,
            path=path,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return failure(request, 500, "INTERNAL_ERROR", "The request could not be completed.")
