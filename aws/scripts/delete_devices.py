from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Iterable

import boto3
from botocore.exceptions import ClientError


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _is_not_found(exc: ClientError) -> bool:
    return _error_code(exc) in {"ResourceNotFoundException", "NotFoundException"}


def _local_things(cert_dir: Path, prefix: str) -> set[str]:
    if not cert_dir.exists():
        return set()
    return {
        path.name
        for path in cert_dir.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    }


def _cloud_things(iot, prefix: str) -> set[str]:
    """Discover managed simulator Things.

    AWS IoT list_things has no prefix filter, so discovery is intentionally opt-in
    and filters client-side. The prefix guard prevents this tool from touching
    unrelated Things in the account.
    """
    out: set[str] = set()
    kwargs: dict[str, object] = {"maxResults": 250}
    while True:
        response = iot.list_things(**kwargs)
        for row in response.get("things", []):
            name = str(row.get("thingName", ""))
            if name.startswith(prefix):
                out.add(name)
        token = response.get("nextToken")
        if not token:
            break
        kwargs["nextToken"] = token
    return out


def _thing_principals(iot, thing_name: str) -> list[str]:
    try:
        return list(iot.list_thing_principals(thingName=thing_name).get("principals", []))
    except ClientError as exc:
        if _is_not_found(exc):
            return []
        raise


def _detach_principal_policies(iot, principal: str, dry_run: bool) -> None:
    try:
        policies = iot.list_attached_policies(target=principal, recursive=False).get("policies", [])
    except ClientError as exc:
        if _is_not_found(exc):
            return
        raise
    for policy in policies:
        name = str(policy.get("policyName", ""))
        if not name:
            continue
        if dry_run:
            print(f"  would detach policy {name} from {principal}")
        else:
            try:
                iot.detach_policy(policyName=name, target=principal)
            except ClientError as exc:
                if not _is_not_found(exc):
                    raise


def _delete_certificate_principal(iot, principal: str, dry_run: bool) -> None:
    marker = ":cert/"
    if marker not in principal:
        return
    cert_id = principal.rsplit("/", 1)[-1]
    if dry_run:
        print(f"  would deactivate/delete certificate {cert_id}")
        return
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


def delete_thing(iot, thing_name: str, cert_dir: Path, dry_run: bool = False) -> list[str]:
    """Delete one managed simulator Thing and all certificate principals attached to it.

    Returns a list of human-readable errors. Local certificate material is removed
    only when all cloud cleanup steps for the Thing succeeded.
    """
    errors: list[str] = []
    principals = _thing_principals(iot, thing_name)

    # Include the locally recorded ARN if AWS no longer reports it as attached.
    arn_file = cert_dir / thing_name / "certificate-arn.txt"
    if arn_file.exists():
        local_arn = arn_file.read_text(encoding="utf-8").strip()
        if local_arn and local_arn not in principals:
            principals.append(local_arn)

    for principal in principals:
        try:
            _detach_principal_policies(iot, principal, dry_run)
            if dry_run:
                print(f"  would detach principal from {thing_name}: {principal}")
            else:
                try:
                    iot.detach_thing_principal(thingName=thing_name, principal=principal)
                except ClientError as exc:
                    if not _is_not_found(exc):
                        raise
            _delete_certificate_principal(iot, principal, dry_run)
        except Exception as exc:  # keep cleaning other principals, but surface failure
            errors.append(f"{thing_name}: principal cleanup failed for {principal}: {exc}")

    try:
        if dry_run:
            print(f"  would delete Thing {thing_name}")
        else:
            try:
                iot.delete_thing(thingName=thing_name)
            except ClientError as exc:
                if not _is_not_found(exc):
                    raise
    except Exception as exc:
        errors.append(f"{thing_name}: Thing deletion failed: {exc}")

    local_dir = cert_dir / thing_name
    if not errors and local_dir.exists():
        if dry_run:
            print(f"  would remove local directory {local_dir}")
        else:
            shutil.rmtree(local_dir)

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete QuakeMesh simulator IoT Things and certificates safely")
    parser.add_argument("--cert-dir", default="artifacts/iot-devices")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "ap-south-1"))
    parser.add_argument("--prefix", default="QM-SIM-")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="also discover all cloud Things with --prefix (recommended before CDK destroy)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.prefix or len(args.prefix) < 3:
        parser.error("--prefix must be at least 3 characters")

    cert_dir = Path(args.cert_dir)
    iot = boto3.client("iot", region_name=args.region)
    names = _local_things(cert_dir, args.prefix)
    if args.discover:
        names |= _cloud_things(iot, args.prefix)

    if not names:
        print("No matching simulator Things found.")
        return

    all_errors: list[str] = []
    for thing in sorted(names):
        print(f"Cleaning {thing}")
        errors = delete_thing(iot, thing, cert_dir, args.dry_run)
        all_errors.extend(errors)
        if not errors:
            print(f"  {'would delete' if args.dry_run else 'deleted'} {thing}")

    if all_errors:
        print("\nCleanup completed with errors:")
        for error in all_errors:
            print(f"- {error}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
