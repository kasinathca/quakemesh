from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import boto3


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cloudformation = boto3.client("cloudformation", region_name=args.region)
    gateway = boto3.client("apigateway", region_name=args.region)
    iot = boto3.client("iot", region_name=args.region)
    identity = boto3.client("sts", region_name=args.region).get_caller_identity()
    stack = cloudformation.describe_stacks(StackName=args.stack_name)["Stacks"][0]
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}
    if outputs.get("SessionId") != args.session_id:
        raise RuntimeError("stack output does not match requested session")
    key = gateway.get_api_key(apiKey=outputs["ApiKeyId"], includeValue=True)["value"]
    config = {
        "schema_version": "2.0",
        "stack_name": args.stack_name,
        "stack_id": stack["StackId"],
        "session_id": args.session_id,
        "account_id": identity["Account"],
        "region": args.region,
        "created_at": stack["CreationTime"].astimezone(timezone.utc).isoformat(),
        "expires_at": outputs["ExpiresAt"],
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "api_base_url": outputs["ApiBaseUrl"],
        "api_key": key,
        "iot_endpoint": iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"],
        "device_policy_name": outputs["DevicePolicyName"],
        "tables": {
            "devices": outputs["DeviceTableName"],
            "evidence": outputs["EvidenceTableName"],
            "events": outputs["EventTableName"],
            "alerts": outputs["AlertTableName"],
        },
    }
    if outputs.get("SnsPlatformApplicationArn"):
        config["sns_platform_application_arn"] = outputs["SnsPlatformApplicationArn"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {args.output}; it contains a controlled-demo API key and is gitignored.")


if __name__ == "__main__":
    main()
