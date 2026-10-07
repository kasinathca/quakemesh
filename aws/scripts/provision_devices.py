from __future__ import annotations

import argparse
import os
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _is_not_found(exc: ClientError) -> bool:
    return _error_code(exc) in {"ResourceNotFoundException", "NotFoundException"}


def root_ca(path: Path) -> None:
    if path.exists() and path.stat().st_size > 500:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    url = "https://www.amazontrust.com/repository/AmazonRootCA1.pem"
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, path)


def _cert_status(iot, arn: str) -> str | None:
    cert_id = arn.rsplit("/", 1)[-1]
    try:
        return str(iot.describe_certificate(certificateId=cert_id)["certificateDescription"]["status"])
    except ClientError as exc:
        if _is_not_found(exc):
            return None
        raise


def local_active_certificate(iot, directory: Path) -> str | None:
    arn_file = directory / "certificate-arn.txt"
    cert_file = directory / "certificate.pem.crt"
    key_file = directory / "private.pem.key"
    if not (arn_file.exists() and cert_file.exists() and key_file.exists()):
        return None
    arn = arn_file.read_text(encoding="utf-8").strip()
    return arn if arn and _cert_status(iot, arn) == "ACTIVE" else None


def _detach_and_delete_certificate(iot, thing_name: str, principal: str) -> None:
    """Remove a stale certificate principal belonging to a managed simulator Thing."""
    try:
        for policy in iot.list_attached_policies(target=principal, recursive=False).get("policies", []):
            name = str(policy.get("policyName", ""))
            if name:
                iot.detach_policy(policyName=name, target=principal)
    except ClientError as exc:
        if not _is_not_found(exc):
            raise
    try:
        iot.detach_thing_principal(thingName=thing_name, principal=principal)
    except ClientError as exc:
        if not _is_not_found(exc):
            raise
    if ":cert/" in principal:
        cert_id = principal.rsplit("/", 1)[-1]
        try:
            iot.update_certificate(certificateId=cert_id, newStatus="INACTIVE")
        except ClientError as exc:
            if not _is_not_found(exc):
                raise
        try:
            iot.delete_certificate(certificateId=cert_id, forceDelete=True)
        except ClientError as exc:
            if not _is_not_found(exc):
                raise


def _prune_stale_principals(iot, thing_name: str, keep_arn: str | None) -> None:
    try:
        principals = list(iot.list_thing_principals(thingName=thing_name).get("principals", []))
    except ClientError as exc:
        if _is_not_found(exc):
            principals = []
        else:
            raise
    for principal in principals:
        if principal == keep_arn:
            continue
        # These Thing names are created solely by this simulator provisioner. An
        # attached certificate whose private key is not the current local key is
        # unusable by the simulator and is removed to avoid orphan credentials.
        _detach_and_delete_certificate(iot, thing_name, principal)


def _remove_stale_local_material(directory: Path) -> None:
    for name in ("certificate.pem.crt", "private.pem.key", "certificate-arn.txt"):
        path = directory / name
        if path.exists():
            path.unlink()


def _write_secret(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        # Windows ACLs are not POSIX modes; .gitignore remains the primary guard.
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision independent QuakeMesh AWS IoT simulator Things")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--out", default="artifacts/iot-devices")
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    if not 1 <= args.count <= 500:
        parser.error("--count must be 1..500")
    if not args.prefix or len(args.prefix) < 3:
        parser.error("--prefix must be at least 3 characters")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root_ca(out.parent / "AmazonRootCA1.pem")
    iot = boto3.client("iot", region_name=args.region)

    # Fail before creating anything if the CDK-managed policy is absent.
    policy_name = f"QuakeMeshV2-{args.session_id}-DevicePolicy"
    iot.get_policy(policyName=policy_name)
    endpoint = iot.describe_endpoint(endpointType="iot:Data-ATS")["endpointAddress"]

    for index in range(1, args.count + 1):
        thing = f"{args.prefix}{index:04d}"
        directory = out / thing
        directory.mkdir(parents=True, exist_ok=True)
        try:
            created = iot.create_thing(
                thingName=thing,
                attributePayload={"attributes": {"Project": "QuakeMesh", "SessionId": args.session_id}},
            )
            if created.get("thingArn"):
                iot.tag_resource(resourceArn=created["thingArn"], tags=[{"Key":"Project","Value":"QuakeMesh"},{"Key":"SessionId","Value":args.session_id}])
        except ClientError as exc:
            if _error_code(exc) != "ResourceAlreadyExistsException":
                raise

        arn = local_active_certificate(iot, directory)
        if arn:
            _prune_stale_principals(iot, thing, keep_arn=arn)
            iot.attach_thing_principal(thingName=thing, principal=arn)
            iot.attach_policy(policyName=policy_name, target=arn)
            print("reused", thing)
            continue

        # A stale local ARN or an AWS-side certificate without a matching local
        # private key cannot be recovered. Remove it before issuing a replacement.
        _prune_stale_principals(iot, thing, keep_arn=None)
        _remove_stale_local_material(directory)

        cert = iot.create_keys_and_certificate(setAsActive=True)
        cert_arn = str(cert["certificateArn"])
        try:
            _write_secret(directory / "certificate.pem.crt", str(cert["certificatePem"]))
            _write_secret(directory / "private.pem.key", str(cert["keyPair"]["PrivateKey"]))
            (directory / "certificate-arn.txt").write_text(cert_arn, encoding="utf-8")
            iot.attach_thing_principal(thingName=thing, principal=cert_arn)
            iot.attach_policy(policyName=policy_name, target=cert_arn)
        except Exception:
            # Avoid leaving a newly issued but unusable credential in the account.
            try:
                _detach_and_delete_certificate(iot, thing, cert_arn)
            finally:
                _remove_stale_local_material(directory)
            raise
        print("provisioned", thing)

    (out.parent / "iot-endpoint.txt").write_text(str(endpoint), encoding="utf-8")
    print("endpoint", endpoint)


if __name__ == "__main__":
    main()
