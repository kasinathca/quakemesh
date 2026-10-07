from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import boto3
from boto3.dynamodb.types import TypeDeserializer

API_SCHEMA_VERSION = "2.0"
_deserializer = TypeDeserializer()


def stream_image(image: dict) -> dict:
    return {key: _deserializer.deserialize(value) for key, value in image.items()}


def env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"missing environment variable {name}")
    return value


def now_ms() -> int:
    return int(time.time() * 1000)


def request_id(event: dict | None = None, context: Any = None) -> str:
    event = event or {}
    gateway_id = event.get("requestContext", {}).get("requestId")
    lambda_id = getattr(context, "aws_request_id", None)
    return str(gateway_id or lambda_id or uuid.uuid4())


def json_response(status: int, body: dict, headers: dict | None = None) -> dict:
    response_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    response_headers.update(headers or {})
    return {
        "statusCode": status,
        "headers": response_headers,
        "body": json.dumps(body, separators=(",", ":")),
    }


def success(request: str, data: Any, status: int = 200) -> dict:
    return json_response(
        status,
        {"schema_version": API_SCHEMA_VERSION, "request_id": request, "data": data},
        {"X-Request-ID": request},
    )


def failure(
    request: str,
    status: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> dict:
    return json_response(
        status,
        {
            "schema_version": API_SCHEMA_VERSION,
            "error": {
                "code": code,
                "message": message,
                "request_id": request,
                "details": details or {},
            },
        },
        {"X-Request-ID": request},
    )


def log(stage: str, request: str | None = None, **fields: Any) -> None:
    payload = {
        "level": "INFO",
        "pipeline_stage": stage,
        "session_id": os.getenv("QM_SESSION_ID", "unknown"),
    }
    if request:
        payload["request_id"] = request
    payload.update({key: value for key, value in fields.items() if value is not None})
    print(json.dumps(payload, separators=(",", ":"), default=str))
