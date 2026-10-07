from __future__ import annotations

import json
import os
from decimal import Decimal

from botocore.exceptions import ClientError

from quakemesh_core.geo import H3GeoIndex
from quakemesh_core.validation import ValidationError

from .common import boto3, env, failure, log, now_ms, request_id, success
from .ingress import process

_geo = None


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
    return _table(table_name).scan(Limit=limit).get("Items", [])


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
    if payload.get("acknowledgement_source") != "android":
        raise ValidationError("acknowledgement_source must be android")
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
                    ":source": "android",
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
            for row in rows:
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
        return failure(request, 404, "ROUTE_NOT_FOUND", "The requested route was not found.")
    except json.JSONDecodeError:
        return failure(request, 400, "REQUEST_VALIDATION_FAILED", "Request body must be valid JSON.")
    except ValidationError as error:
        return failure(request, 422, "REQUEST_VALIDATION_FAILED", str(error))
    except ValueError as error:
        return failure(request, 422, "REQUEST_VALIDATION_FAILED", str(error))
    except Exception:
        log("API_REQUEST_FAILED", request, method=method, path=path)
        return failure(request, 500, "INTERNAL_ERROR", "The request could not be completed.")
