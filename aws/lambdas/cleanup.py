from __future__ import annotations

from botocore.exceptions import ClientError

from .common import boto3, env, log


def _not_found(error: ClientError) -> bool:
    return str(error.response.get("Error", {}).get("Code", "")) in {
        "ResourceNotFoundException",
        "NotFoundException",
    }


def owned_things(iot, session_id: str) -> list[dict]:
    """Return only Things carrying the exact session attribute and name prefix."""
    prefix = f"QM-{session_id}-SIM-"
    found: list[dict] = []
    token: str | None = None
    while True:
        request = {
            "attributeName": "SessionId",
            "attributeValue": session_id,
            "maxResults": 250,
        }
        if token:
            request["nextToken"] = token
        response = iot.list_things(**request)
        for thing in response.get("things", []):
            attributes = thing.get("attributes", {})
            if (
                str(thing.get("thingName", "")).startswith(prefix)
                and attributes.get("Project") == "QuakeMesh"
                and attributes.get("SessionId") == session_id
            ):
                found.append(thing)
        token = response.get("nextToken")
        if not token:
            return found


def delete_owned_thing(iot, thing_name: str, policy_name: str) -> None:
    """Delete one owned simulator Thing without touching a shared principal."""
    try:
        principals = list(iot.list_thing_principals(thingName=thing_name).get("principals", []))
    except ClientError as error:
        if _not_found(error):
            return
        raise

    for principal in principals:
        if ":cert/" not in principal:
            raise RuntimeError(f"Refusing non-certificate principal on owned Thing {thing_name}")
        attached_things = set(iot.list_principal_things(principal=principal).get("things", []))
        if attached_things - {thing_name}:
            raise RuntimeError(f"Refusing shared certificate on owned Thing {thing_name}")
        policies = {
            str(item.get("policyName", ""))
            for item in iot.list_attached_policies(target=principal, recursive=False).get("policies", [])
            if item.get("policyName")
        }
        if policies - {policy_name}:
            raise RuntimeError(f"Refusing certificate with unexpected policy on owned Thing {thing_name}")
        if policy_name in policies:
            iot.detach_policy(policyName=policy_name, target=principal)
        iot.detach_thing_principal(thingName=thing_name, principal=principal)
        certificate_id = principal.rsplit("/", 1)[-1]
        iot.update_certificate(certificateId=certificate_id, newStatus="INACTIVE")
        iot.delete_certificate(certificateId=certificate_id, forceDelete=True)

    iot.delete_thing(thingName=thing_name)


def handler(event, context):
    session_id = env("QM_SESSION_ID")
    stack_name = env("QM_STACK_NAME")
    policy_name = env("QM_IOT_POLICY_NAME")
    region = env("AWS_REGION")
    iot = boto3.client("iot", region_name=region)
    cloudformation = boto3.client("cloudformation", region_name=region)

    things = owned_things(iot, session_id)
    log("SESSION_EXPIRY_CLEANUP_STARTED", session_id=session_id, owned_thing_count=len(things))
    for thing in things:
        name = str(thing["thingName"])
        delete_owned_thing(iot, name, policy_name)
        log("SESSION_IOT_THING_DELETED", session_id=session_id, device_id=name)

    # This call is intentionally last. Any ownership or IoT cleanup failure leaves
    # the stack in place so Scheduler retries can continue safely.
    cloudformation.delete_stack(StackName=stack_name)
    log("SESSION_STACK_DELETE_REQUESTED", session_id=session_id, stack_name=stack_name)
    return {"session_id": session_id, "stack_name": stack_name, "deleted_things": len(things)}
