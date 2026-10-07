from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def call(base_url: str, path: str, method: str = "GET", body: dict | None = None, api_key: str | None = None) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, separators=(",", ":")).encode()
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"{method} {path} failed: HTTP {error.code} {error.read().decode()}") from error
    if payload.get("schema_version") != "2.0" or not payload.get("request_id"):
        raise RuntimeError(f"{method} {path} did not return a V2 envelope")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    base_url = config["api_base_url"]
    api_key = config["api_key"]
    device_id = f"QM-AWS-SMOKE-{int(time.time())}"
    now = int(time.time() * 1000)
    health = call(base_url, "/health")["data"]
    if health.get("session_id") != config["session_id"]:
        raise RuntimeError("health session does not match runtime configuration")
    heartbeat = call(
        base_url,
        "/v1/devices/heartbeat",
        "POST",
        {
            "schema_version": "1.0",
            "device_id": device_id,
            "seq": 1,
            "observed_at_ms": now,
            "latitude": 12.9716,
            "longitude": 77.5946,
        },
        api_key,
    )
    trigger = call(
        base_url,
        "/v1/evidence/trigger",
        "POST",
        {
            "schema_version": "1.0",
            "device_id": device_id,
            "seq": 2,
            "observed_at_ms": now + 1,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "motion_rms": 1.2,
            "motion_peak": 2.2,
        },
        api_key,
    )
    devices = call(base_url, "/v1/devices?limit=200")["data"]["items"]
    if not any(item.get("device_id") == device_id for item in devices):
        raise RuntimeError("smoke device was not queryable through the AWS V2 API")
    print(json.dumps({
        "status": "PASS",
        "session_id": config["session_id"],
        "device_id": device_id,
        "heartbeat": heartbeat["data"],
        "trigger": trigger["data"],
    }, indent=2))


if __name__ == "__main__":
    main()
