from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError

NOT_FOUND = {"NotFoundException", "ResourceNotFoundException", "ResourceNotFoundFault"}


def issue(service: str, error: ClientError) -> dict[str, str]:
    detail = error.response.get("Error", {})
    return {"service": service, "code": str(detail.get("Code", "")), "message": str(detail.get("Message", ""))}


def absent_check(
    name: str,
    service: str,
    identifier: str,
    call: Callable[[], Any],
    empty: Callable[[Any], bool] | None = None,
) -> tuple[dict[str, str], dict[str, str] | None, dict[str, str] | None]:
    try:
        response = call()
        if empty and empty(response):
            return {"name": name, "status": "PASS", "detail": "absent"}, None, None
        return (
            {"name": name, "status": "FAIL", "detail": identifier},
            {"type": name, "id": identifier},
            None,
        )
    except ClientError as error:
        detail = error.response.get("Error", {})
        code = str(detail.get("Code", ""))
        message = str(detail.get("Message", ""))
        if code in NOT_FOUND or (code == "ValidationError" and "does not exist" in message):
            return {"name": name, "status": "PASS", "detail": "absent"}, None, None
        return {"name": name, "status": "UNKNOWN", "detail": f"{code}: {message}"}, None, issue(service, error)


def load_json(path: Path | None) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stack-name", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--region", default="ap-south-1")
    parser.add_argument("--runtime-config", type=Path)
    parser.add_argument("--resource-inventory", type=Path)
    parser.add_argument("--cdk-assets", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    findings: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    checks: list[dict[str, str]] = []
    runtime = load_json(args.runtime_config)
    inventory = load_json(args.resource_inventory)
    assets_manifest = load_json(args.cdk_assets)

    def record(result: tuple[dict[str, str], dict[str, str] | None, dict[str, str] | None]) -> None:
        check, finding, error = result
        checks.append(check)
        if finding:
            findings.append(finding)
        if error:
            errors.append(error)

    cloudformation = boto3.client("cloudformation", region_name=args.region)
    record(absent_check("cloudformation_stack", "cloudformation", args.stack_name, lambda: cloudformation.describe_stacks(StackName=args.stack_name)))

    try:
        tagging = boto3.client("resourcegroupstaggingapi", region_name=args.region)
        tagged: list[str] = []
        token = ""
        while True:
            request: dict[str, Any] = {"TagFilters": [{"Key": "Project", "Values": ["QuakeMesh"]}, {"Key": "SessionId", "Values": [args.session_id]}]}
            if token:
                request["PaginationToken"] = token
            response = tagging.get_resources(**request)
            tagged.extend(str(row["ResourceARN"]) for row in response.get("ResourceTagMappingList", []))
            token = str(response.get("PaginationToken", ""))
            if not token:
                break
        checks.append({"name": "session_tagged_resources", "status": "PASS" if not tagged else "FAIL", "detail": "absent" if not tagged else f"{len(tagged)} remain"})
        findings.extend({"type": "tagged_resource", "id": arn} for arn in tagged)
    except ClientError as error:
        checks.append({"name": "session_tagged_resources", "status": "UNKNOWN", "detail": "inspection failed"})
        errors.append(issue("resourcegroupstaggingapi", error))

    iot = boto3.client("iot", region_name=args.region)
    prefix = f"QM-{args.session_id}-"
    try:
        things: list[str] = []
        token: str | None = None
        while True:
            request = {"maxResults": 250}
            if token:
                request["nextToken"] = token
            response = iot.list_things(**request)
            things.extend(str(row["thingName"]) for row in response.get("things", []) if str(row.get("thingName", "")).startswith(prefix))
            token = response.get("nextToken")
            if not token:
                break
        checks.append({"name": "iot_things", "status": "PASS" if not things else "FAIL", "detail": "absent" if not things else f"{len(things)} remain"})
        findings.extend({"type": "iot_thing", "id": name} for name in things)
    except ClientError as error:
        checks.append({"name": "iot_things", "status": "UNKNOWN", "detail": "inspection failed"})
        errors.append(issue("iot", error))

    try:
        certificates: list[str] = []
        marker: str | None = None
        while True:
            request = {"pageSize": 250}
            if marker:
                request["marker"] = marker
            response = iot.list_certificates(**request)
            for certificate in response.get("certificates", []):
                arn = str(certificate.get("certificateArn", ""))
                tags = {str(tag["Key"]): str(tag["Value"]) for tag in iot.list_tags_for_resource(resourceArn=arn).get("tags", [])}
                if tags.get("Project") == "QuakeMesh" and tags.get("SessionId") == args.session_id:
                    certificates.append(arn)
            marker = response.get("nextMarker")
            if not marker:
                break
        checks.append({"name": "iot_certificates", "status": "PASS" if not certificates else "FAIL", "detail": "absent" if not certificates else f"{len(certificates)} remain"})
        findings.extend({"type": "iot_certificate", "id": arn} for arn in certificates)
    except ClientError as error:
        checks.append({"name": "iot_certificates", "status": "UNKNOWN", "detail": "inspection failed"})
        errors.append(issue("iot", error))

    clients: dict[str, Any] = {}

    def client(service: str):
        clients.setdefault(service, boto3.client(service, region_name=args.region))
        return clients[service]

    verifiers: dict[str, tuple[str, Callable[[str], Any], Callable[[Any], bool] | None]] = {
        "AWS::DynamoDB::Table": ("dynamodb", lambda value: client("dynamodb").describe_table(TableName=value), None),
        "AWS::Lambda::Function": ("lambda", lambda value: client("lambda").get_function(FunctionName=value), None),
        "AWS::Lambda::LayerVersion": ("lambda", lambda value: client("lambda").get_layer_version_by_arn(Arn=value), None),
        "AWS::ApiGateway::RestApi": ("apigateway", lambda value: client("apigateway").get_rest_api(restApiId=value), None),
        "AWS::ApiGateway::ApiKey": ("apigateway", lambda value: client("apigateway").get_api_key(apiKey=value, includeValue=False), None),
        "AWS::ApiGateway::UsagePlan": ("apigateway", lambda value: client("apigateway").get_usage_plan(usagePlanId=value), None),
        "AWS::Scheduler::Schedule": ("scheduler", lambda value: client("scheduler").get_schedule(Name=value), None),
        "AWS::Events::Rule": ("events", lambda value: client("events").describe_rule(Name=value), None),
        "AWS::Logs::LogGroup": ("logs", lambda value: client("logs").describe_log_groups(logGroupNamePrefix=value, limit=1), lambda response: not response.get("logGroups")),
        "AWS::IoT::Policy": ("iot", lambda value: iot.get_policy(policyName=value), None),
        "AWS::CloudWatch::Alarm": ("cloudwatch", lambda value: client("cloudwatch").describe_alarms(AlarmNames=[value]), lambda response: not response.get("MetricAlarms") and not response.get("CompositeAlarms")),
        "AWS::IAM::Role": ("iam", lambda value: client("iam").get_role(RoleName=value), None),
    }
    type_counts: dict[str, int] = {}
    for resource in inventory.get("resources", []):
        resource_type = str(resource.get("type", ""))
        physical_id = str(resource.get("physical_id", ""))
        if not physical_id or resource_type not in verifiers:
            continue
        service, factory, empty = verifiers[resource_type]
        type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
        record(absent_check(resource_type, service, physical_id, lambda value=physical_id, call=factory: call(value), empty))

    api_id = ""
    if runtime.get("api_base_url"):
        api_id = (urlparse(str(runtime["api_base_url"])).hostname or "").split(".", 1)[0]
    if api_id and not any(row.get("type") == "AWS::ApiGateway::RestApi" for row in inventory.get("resources", [])):
        record(absent_check("api_gateway", "apigateway", api_id, lambda: client("apigateway").get_rest_api(restApiId=api_id)))

    platform_arn = runtime.get("sns_platform_application_arn")
    if platform_arn:
        try:
            sns = client("sns")
            endpoints: list[str] = []
            token = ""
            while True:
                request = {"PlatformApplicationArn": platform_arn}
                if token:
                    request["NextToken"] = token
                response = sns.list_endpoints_by_platform_application(**request)
                endpoints.extend(str(row["EndpointArn"]) for row in response.get("Endpoints", []) if row.get("Attributes", {}).get("CustomUserData") == f"QuakeMesh:{args.session_id}")
                token = str(response.get("NextToken", ""))
                if not token:
                    break
            checks.append({"name": "sns_platform_endpoints", "status": "PASS" if not endpoints else "FAIL", "detail": "absent" if not endpoints else f"{len(endpoints)} remain"})
            findings.extend({"type": "sns_platform_endpoint", "id": arn} for arn in endpoints)
        except ClientError as error:
            checks.append({"name": "sns_platform_endpoints", "status": "UNKNOWN", "detail": "inspection failed"})
            errors.append(issue("sns", error))
    else:
        checks.append({"name": "sns_platform_endpoints", "status": "NOT_APPLICABLE", "detail": "FCM platform application was not configured"})

    bootstrap_assets: list[dict[str, str]] = []
    seen_assets: set[tuple[str, str]] = set()
    for file_asset in assets_manifest.get("files", {}).values():
        for destination in file_asset.get("destinations", {}).values():
            bucket = str(destination.get("bucketName", ""))
            key = str(destination.get("objectKey", ""))
            region = str(destination.get("region", args.region))
            if not bucket or not key or (bucket, key) in seen_assets:
                continue
            seen_assets.add((bucket, key))
            try:
                boto3.client("s3", region_name=region).head_object(Bucket=bucket, Key=key)
                bootstrap_assets.append({"bucket": bucket, "key": key, "status": "PRESENT_SHARED_NOT_DELETED"})
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code in {"404", "NoSuchKey", "NotFound"}:
                    bootstrap_assets.append({"bucket": bucket, "key": key, "status": "ABSENT"})
                else:
                    bootstrap_assets.append({"bucket": bucket, "key": key, "status": "UNKNOWN"})
                    errors.append(issue("s3", error))

    status = "CLEAN" if not findings and not errors else "INCOMPLETE"
    report = {
        "schema_version": "2.0",
        "status": status,
        "session_id": args.session_id,
        "stack_name": args.stack_name,
        "region": args.region,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "inventory_verified_counts": type_counts,
        "findings": findings,
        "errors": errors,
        "bootstrap": {
            "scope": "shared CDKToolkit; not deleted by session teardown",
            "asset_policy": "content-addressed assets are retained because exclusive ownership cannot be proven",
            "assets": bootstrap_assets,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status == "CLEAN" else 2


if __name__ == "__main__":
    sys.exit(main())
