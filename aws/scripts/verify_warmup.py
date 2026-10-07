from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path


def read(base_url: str, path: str) -> dict:
    request = urllib.request.Request(base_url.rstrip("/") + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    if payload.get("schema_version") != "2.0" or not payload.get("request_id"):
        raise RuntimeError(f"{path} did not return a V2 envelope")
    return payload["data"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--minimum-devices", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    deadline = time.monotonic() + args.timeout_seconds
    last = {}
    while time.monotonic() < deadline:
        devices = read(config["api_base_url"], "/v1/devices?limit=500").get("items", [])
        events = read(config["api_base_url"], "/v1/events?limit=200").get("items", [])
        alerts = read(config["api_base_url"], "/v1/alerts?limit=500").get("items", [])
        scenario_devices = [
            item
            for item in devices
            if item.get("provenance_type") == "scenario"
            and item.get("scenario_run_id") == config["session_id"]
        ]
        confirmed = [
            item
            for item in events
            if item.get("status") == "CONFIRMED"
            and item.get("provenance_type") == "scenario"
            and item.get("scenario_run_id") == config["session_id"]
            and len(set(item.get("device_ids", []))) >= args.minimum_devices
            and len(set(item.get("detection_footprint", []))) >= 3
            and item.get("warning_frontier")
        ]
        event_ids = {item["event_id"] for item in confirmed}
        matching_alerts = [item for item in alerts if item.get("event_id") in event_ids]
        last = {
            "scenario_devices": len(scenario_devices),
            "confirmed_events": len(confirmed),
            "alerts": len(matching_alerts),
        }
        if len(scenario_devices) >= args.minimum_devices and confirmed and matching_alerts:
            print(json.dumps({"status": "PASS", **last}, indent=2))
            return
        time.sleep(2)
    raise RuntimeError(f"AWS distributed warm-up did not reach authoritative success: {last}")


if __name__ == "__main__":
    main()
