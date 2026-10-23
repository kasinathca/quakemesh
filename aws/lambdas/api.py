from __future__ import annotations

import json
import hmac
import os
import re
import uuid
from decimal import Decimal
from urllib.parse import unquote

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Attr

from .common import boto3, env, failure, log, now_ms, request_id, success
from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.validation import ValidationError

from .ingress import process

_geo = None
_operator_credential = None
sns = boto3.client("sns")
lambda_client = boto3.client("lambda")
secretsmanager = boto3.client("secretsmanager")
CONTROLLED_TEST_LABEL = "CONTROLLED TEST — NOT AN EARTHQUAKE ALERT"
_TEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,79}$")

AWS_SCENARIOS = {
    "isolated": ("Isolated shaking", "NO_CONFIRMATION"),
    "same-cell": ("Same-cell movement", "NO_CONFIRMATION"),
    "distributed": ("Distributed earthquake", "CONFIRMATION"),
    "degraded": ("Degraded network", "CONDITIONAL"),
    "false-positive": ("False-positive demonstration", "NO_CONFIRMATION"),
}


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


def _latest_reference_device() -> dict | None:
    rows = _items("QM_DEVICE_TABLE", 1000)
    current = now_ms()
    eligible = [
        row for row in rows
        if row.get("provenance_type") == "physical"
        and row.get("h3_cell")
        and current - int(row.get("last_seen_ms", 0)) <= 120_000
    ]
    return max(eligible, key=lambda row: int(row.get("last_seen_ms", 0)), default=None)


def _scenario_view(row: dict) -> dict:
    clean = _clean(row)
    clean.pop("reference_device_id", None)
    clean.pop("reference_h3_cell", None)
    return clean


def _scenario_catalog() -> list[dict]:
    common = [
        {"name": "devices", "type": "integer", "default": 25, "minimum": 4, "maximum": 100, "unit": "devices"},
        {"name": "seed", "type": "integer", "default": 42, "minimum": 0, "maximum": 2147483647, "unit": "integer"},
        {"name": "trigger_propagation_interval_ms", "type": "integer", "default": 70, "minimum": 0, "maximum": 1000, "unit": "milliseconds"},
    ]
    result = []
    for scenario_id, (title, expected) in AWS_SCENARIOS.items():
        params = list(common)
        if scenario_id == "degraded":
            params += [
                {"name": "packet_loss_fraction", "type": "number", "default": 0.25, "minimum": 0, "maximum": 0.95, "unit": "fraction"},
                {"name": "network_jitter_ms", "type": "integer", "default": 900, "minimum": 0, "maximum": 5000, "unit": "milliseconds"},
            ]
        result.append({"id": scenario_id, "title": title, "purpose": "Cloud execution using the registered phone H3 cell as the geographic reference.", "expected_result": expected, "catalog_version": "2.1", "supported_parameters": params})
    return result


def _validate_scenario_parameters(scenario: str, supplied: dict) -> dict:
    definition = next(item for item in _scenario_catalog() if item["id"] == scenario)
    specs = {item["name"]: item for item in definition["supported_parameters"]}
    unknown = set(supplied) - set(specs)
    if unknown:
        raise ValidationError(f"unsupported parameter(s): {', '.join(sorted(unknown))}")
    normalized = {}
    for name, spec in specs.items():
        value = supplied.get(name, spec["default"])
        if spec["type"] == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
            raise ValidationError(f"{name} must be an integer")
        if spec["type"] == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            raise ValidationError(f"{name} must be a number")
        if value < spec["minimum"] or value > spec["maximum"]:
            raise ValidationError(f"{name} must be between {spec['minimum']} and {spec['maximum']}")
        normalized[name] = Decimal(str(value)) if isinstance(value, float) else value
    return normalized


def _start_scenario(event: dict, request: str) -> dict:
    payload = json.loads(event.get("body") or "{}")
    scenario = payload.get("scenario")
    if scenario not in AWS_SCENARIOS:
        raise ValidationError("unknown scenario")
    parameters = _validate_scenario_parameters(str(scenario), payload.get("parameters") or {})
    reference = _latest_reference_device()
    if not reference:
        return failure(request, 409, "PHONE_LOCATION_UNAVAILABLE", "No physical phone has a current registered H3 location. Start monitoring on the phone and retry.")
    run_id = f"aws-{now_ms()}-{uuid.uuid4().hex[:8]}"
    timestamp = now_ms()
    row = {
        "run_id": run_id, "scenario": scenario, "source": "dashboard", "mode": "AWS",
        "catalog_version": "2.1", "seed": parameters["seed"], "devices": parameters["devices"],
        "status": "QUEUED", "expected_result": AWS_SCENARIOS[str(scenario)][1],
        "observed_result": None, "created_at_ms": timestamp, "started_at_ms": None,
        "completed_at_ms": None, "updated_at_ms": timestamp, "parameters": parameters,
        "event_ids": [], "error": None, "reference_device_id": reference["device_id"],
        "reference_h3_cell": reference["h3_cell"],
    }
    table = _table("QM_SCENARIO_TABLE")
    try:
        table.put_item(Item={"run_id": "ACTIVE", "active_run_id": run_id, "created_at_ms": timestamp}, ConditionExpression="attribute_not_exists(run_id)")
        table.put_item(Item=row, ConditionExpression="attribute_not_exists(run_id)")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return failure(request, 409, "SCENARIO_ALREADY_RUNNING", "Another scenario run is active.")
        raise
    lambda_client.invoke(FunctionName=env("QM_SCENARIO_RUNNER_ARN"), InvocationType="Event", Payload=json.dumps({"run_id": run_id}).encode())
    return success(request, _scenario_view(row), 202)


def _reset_scenario(request: str) -> dict:
    active = _table("QM_SCENARIO_TABLE").get_item(
        Key={"run_id": "ACTIVE"}, ConsistentRead=True
    ).get("Item")
    if active:
        return failure(
            request,
            409,
            "SCENARIO_ALREADY_RUNNING",
            "The active scenario must finish before the dashboard can be reset.",
        )
    return success(
        request,
        {
            "reset": True,
            "evidence_retained": True,
            "message": "Dashboard selection reset; cloud evidence remains available.",
        },
    )


def _scenario_runs(limit: int) -> list[dict]:
    rows = [row for row in _items("QM_SCENARIO_TABLE", limit + 1) if row.get("run_id") != "ACTIVE"]
    rows.sort(key=lambda row: int(row.get("created_at_ms", 0)), reverse=True)
    return [_scenario_view(row) for row in rows[:limit]]


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


def _alert_receipt(event: dict, request: str) -> dict:
    alert_id = unquote(str((event.get("pathParameters") or {}).get("alert_id") or ""))
    payload = json.loads(event.get("body") or "{}")
    device_id = payload.get("device_id")
    state = payload.get("state")
    if not alert_id or not isinstance(device_id, str) or not device_id:
        raise ValidationError("alert_id and device_id are required")
    if state not in {"FCM_RECEIVED", "NOTIFICATION_POSTED", "OPENED", "AUDIO_STARTED", "AUDIO_STOPPED"}:
        raise ValidationError("unsupported receipt state")
    table = _table("QM_ALERT_TABLE")
    existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True).get("Item")
    if not existing:
        return failure(request, 404, "ALERT_NOT_FOUND", "The requested alert was not found.")
    if existing.get("device_id") != device_id or existing.get("session_id") != env("QM_SESSION_ID"):
        return failure(request, 409, "ALERT_DEVICE_MISMATCH", "The receipt does not belong to this device and session.")
    timestamp = now_ms()
    field = state.lower() + "_at_ms"
    table.update_item(
        Key={"alert_id": alert_id},
        UpdateExpression=f"SET {field}=:now,updated_at_ms=:now,last_receipt_state=:state",
        ExpressionAttributeValues={":now": timestamp, ":state": state},
    )
    existing.update({field: timestamp, "updated_at_ms": timestamp, "last_receipt_state": state})
    log("ALERT_RECEIPT", request, alert_id=alert_id, device_id=device_id, state=state)
    return success(request, {"alert": _clean(existing), "transition_created": True})


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
    alert_id = unquote(str((event.get("pathParameters") or {}).get("alert_id") or ""))
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
                if row.get("h3_cell"):
                    row["cell_center"] = list(_geo_index().center(str(row["h3_cell"])))
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
        if method == "GET" and path == "/v1/scenarios":
            return success(request, {"items": _scenario_catalog()})
        if method == "GET" and path == "/v1/scenario-runs":
            return success(request, {"items": _scenario_runs(_bounded_limit(event, 50, 200))})
        if method == "GET" and path.startswith("/v1/scenario-runs/"):
            run_id = str((event.get("pathParameters") or {}).get("run_id") or path.rsplit("/", 1)[-1])
            row = _table("QM_SCENARIO_TABLE").get_item(Key={"run_id": run_id}, ConsistentRead=True).get("Item")
            return success(request, _scenario_view(row)) if row else failure(request, 404, "SCENARIO_RUN_NOT_FOUND", "The scenario run was not found.")
        if method == "GET" and path == "/v1/session":
            active = _table("QM_SCENARIO_TABLE").get_item(Key={"run_id": "ACTIVE"}, ConsistentRead=True).get("Item")
            run = None
            if active:
                run = _table("QM_SCENARIO_TABLE").get_item(Key={"run_id": active["active_run_id"]}, ConsistentRead=True).get("Item")
            return success(request, {"mode": "AWS", "active_run": _scenario_view(run) if run else None, "started_at_ms": run.get("started_at_ms") if run else None, "expires_at_ms": None, "session_id": env("QM_SESSION_ID"), "region": os.getenv("AWS_REGION", "unknown")})
        if method == "POST" and path == "/v1/demo/scenario-runs":
            return _start_scenario(event, request)
        if method == "POST" and path == "/v1/demo/reset":
            return _reset_scenario(request)
        if method == "POST" and path.startswith("/v1/alerts/") and path.endswith("/ack"):
            return _acknowledge(event, request)
        if method == "POST" and path.startswith("/v1/alerts/") and path.endswith("/receipts"):
            return _alert_receipt(event, request)
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
