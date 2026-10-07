from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    findings: list[dict] = []
    errors: list[dict] = []

    cloudformation = boto3.client("cloudformation", region_name=args.region)
    try:
        stack = cloudformation.describe_stacks(StackName=args.stack_name)["Stacks"][0]
        findings.append(
            {"type": "cloudformation_stack", "id": stack["StackId"], "status": stack["StackStatus"]}
        )
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        message = error.response.get("Error", {}).get("Message", "")
        if code != "ValidationError" or "does not exist" not in message:
            errors.append({"service": "cloudformation", "code": code, "message": message})

    try:
        tagging = boto3.client("resourcegroupstaggingapi", region_name=args.region)
        token = ""
        while True:
            kwargs = {
                "TagFilters": [
                    {"Key": "Project", "Values": ["QuakeMesh"]},
                    {"Key": "SessionId", "Values": [args.session_id]},
                ]
            }
            if token:
                kwargs["PaginationToken"] = token
            response = tagging.get_resources(**kwargs)
            findings.extend(
                {"type": "tagged_resource", "id": item["ResourceARN"]}
                for item in response.get("ResourceTagMappingList", [])
            )
            token = response.get("PaginationToken", "")
            if not token:
                break
    except ClientError as error:
        errors.append(
            {
                "service": "resourcegroupstaggingapi",
                "code": error.response.get("Error", {}).get("Code"),
                "message": error.response.get("Error", {}).get("Message", ""),
            }
        )

    try:
        iot = boto3.client("iot", region_name=args.region)
        prefix = f"QM-{args.session_id}-"
        token = None
        while True:
            kwargs = {"maxResults": 250}
            if token:
                kwargs["nextToken"] = token
            response = iot.list_things(**kwargs)
            findings.extend(
                {"type": "iot_thing", "id": thing["thingName"]}
                for thing in response.get("things", [])
                if thing["thingName"].startswith(prefix)
            )
            token = response.get("nextToken")
            if not token:
                break
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code")
        if code != "ResourceNotFoundException":
            errors.append(
                {
                    "service": "iot",
                    "code": code,
                    "message": error.response.get("Error", {}).get("Message", ""),
                }
            )

    status = "CLEAN" if not findings and not errors else "INCOMPLETE"
    report = {
        "schema_version": "2.0",
        "status": status,
        "session_id": args.session_id,
        "stack_name": args.stack_name,
        "region": args.region,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "CLEAN" else 2


if __name__ == "__main__":
    sys.exit(main())
