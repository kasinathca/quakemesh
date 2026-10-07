from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    platform_arn = config.get("sns_platform_application_arn")
    if not platform_arn:
        print("SNS platform application not configured; no session endpoints to delete.")
        return
    session_id = str(config["session_id"])
    marker = f"QuakeMesh:{session_id}"
    sns = boto3.client("sns", region_name=str(config["region"]))
    token = ""
    deleted = 0
    while True:
        request = {"PlatformApplicationArn": platform_arn}
        if token:
            request["NextToken"] = token
        response = sns.list_endpoints_by_platform_application(**request)
        for endpoint in response.get("Endpoints", []):
            if endpoint.get("Attributes", {}).get("CustomUserData") != marker:
                continue
            sns.delete_endpoint(EndpointArn=str(endpoint["EndpointArn"]))
            deleted += 1
        token = str(response.get("NextToken", ""))
        if not token:
            break
    print(f"Deleted {deleted} exact-session SNS platform endpoint(s).")
