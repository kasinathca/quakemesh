from __future__ import annotations

import json
import time
from boto3.dynamodb.conditions import Key
from .common import boto3, env, log, stream_image

iot = boto3.client("iot")
sns = boto3.client("sns")
ddb = boto3.resource("dynamodb")
_iot_data = None


def iot_data():
    global _iot_data
    if _iot_data is None:
        endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]
        _iot_data = boto3.client("iot-data", endpoint_url=f"https://{endpoint}")
    return _iot_data


def targets(cells: list[str], seen_after: int, provenance_type: str, scenario_run_id: str | None) -> list[dict]:
    table = ddb.Table(env("QM_DEVICE_TABLE"))
    found: dict[str, dict] = {}
    for cell in set(cells):
        kwargs = {
            "IndexName": "cell-lastseen-index",
            "KeyConditionExpression": Key("correlation_cell").eq(cell) & Key("last_seen_ms").gte(seen_after),
        }
        while True:
            response = table.query(**kwargs)
            for row in response.get("Items", []):
                if row.get("provenance_type") != provenance_type:
                    continue
                if row.get("scenario_run_id") != scenario_run_id:
                    continue
                found[str(row["device_id"])] = row
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    return list(found.values())


def claim_delivery(event: dict, device_id: str) -> bool:
    """Return True when this invocation should attempt delivery.

    SENT is terminal for an event/device pair. DISPATCHING and FAILED are retryable
    because DynamoDB Streams are at-least-once. If a process dies after the external
    publish but before marking SENT, a later retry can duplicate a message; clients
    therefore deduplicate by alert_id.
    """
    table = ddb.Table(env("QM_ALERT_TABLE"))
    event_id = str(event["event_id"])
    event_version = int(event["version"])
    alert_id = f"{event_id}:{device_id}"
    existing = table.get_item(Key={"alert_id": alert_id}, ConsistentRead=True).get("Item")
    if existing and existing.get("status") == "SENT":
        return False
    now = int(time.time() * 1000)
    table.update_item(
        Key={"alert_id": alert_id},
        UpdateExpression=(
            "SET event_id=:event_id,event_version=:event_version,device_id=:device_id,"
            "created_at_ms=if_not_exists(created_at_ms,:now),updated_at_ms=:now,#s=:dispatching,"
            "attempts=if_not_exists(attempts,:zero)+:one,provenance_type=:provenance,"
            "session_id=:session"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":event_id": event_id,
            ":event_version": event_version,
            ":device_id": device_id,
            ":now": now,
            ":dispatching": "DISPATCHING",
            ":zero": 0,
            ":one": 1,
            ":provenance": str(event.get("provenance_type", "physical")),
            ":session": env("QM_SESSION_ID"),
        },
    )
    if event.get("scenario_run_id"):
        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET scenario_run_id=:run",
            ExpressionAttributeValues={":run": str(event["scenario_run_id"])},
        )
    return True


def mark(alert_id: str, status: str, detail: str | None = None) -> None:
    expression = "SET #s=:s,updated_at_ms=:now"
    values = {":s": status, ":now": int(time.time() * 1000)}
    names = {"#s": "status"}
    if detail:
        expression += ",detail=:d"
        values[":d"] = detail[:1000]
    ddb.Table(env("QM_ALERT_TABLE")).update_item(
        Key={"alert_id": alert_id},
        UpdateExpression=expression,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def send_fcm(endpoint_arn: str, event: dict, alert_id: str, device_id: str, created_at_ms: int) -> None:
    inner = {
        "fcmV1Message": {
            "message": {
                "notification": {
                    "title": "QuakeMesh alert",
                    "body": "Corroborated ground-motion evidence detected in your warning region.",
                },
                "data": {
                    "alert_id": alert_id,
                    "event_id": str(event["event_id"]),
                    "event_version": str(event["version"]),
                    "status": str(event["status"]),
                    "device_id": device_id,
                    "created_at_ms": str(created_at_ms),
                },
                "android": {"priority": "high"},
            }
        }
    }
    sns.publish(
        TargetArn=endpoint_arn,
        Message=json.dumps({"GCM": json.dumps(inner), "default": "QuakeMesh alert"}),
        MessageStructure="json",
    )


def handler(event, context):
    sent: list[str] = []
    for record in event.get("Records", []):
        if record.get("eventName") not in {"INSERT", "MODIFY"}:
            continue
        image = record.get("dynamodb", {}).get("NewImage")
        if not image:
            continue
        event_item = stream_image(image)
        if event_item.get("status") != "CONFIRMED":
            continue
        cells = list(event_item.get("detection_footprint", [])) + list(event_item.get("warning_frontier", []))
        now = int(time.time() * 1000)
        provenance_type = str(event_item.get("provenance_type", "physical"))
        scenario_run_id = event_item.get("scenario_run_id")
        for device in targets(cells, now - 120_000, provenance_type, scenario_run_id):
            device_id = str(device["device_id"])
            version = int(event_item["version"])
            event_id = str(event_item["event_id"])
            alert_id = f"{event_id}:{device_id}"
            if not claim_delivery(event_item, device_id):
                continue
            payload = {
                "schema_version": "1.0",
                "type": "QUAKEMESH_WARNING",
                "event_id": event_id,
                "event_version": version,
                "status": "CONFIRMED",
                "detected_at_ms": int(event_item["updated_at_ms"]),
                "detection_footprint": list(event_item.get("detection_footprint", [])),
                "warning_frontier": list(event_item.get("warning_frontier", [])),
                "alert_id": alert_id,
            }
            try:
                iot_data().publish(
                    topic=f"quakemesh/v1/{env('QM_SESSION_ID')}/devices/{device_id}/alerts",
                    qos=1,
                    payload=json.dumps(payload).encode(),
                )
                if device.get("fcm_endpoint_arn"):
                    send_fcm(str(device["fcm_endpoint_arn"]), event_item, alert_id, device_id, now)
                mark(alert_id, "SENT")
                log("ALERT_DELIVERY_COMPLETED",event_id=event_id,alert_id=alert_id,device_id=device_id,provenance_type=provenance_type,scenario_run_id=scenario_run_id)
                sent.append(device_id)
            except Exception as exc:
                mark(alert_id, "FAILED", repr(exc))
                raise
    return {"sent": sent}
