from __future__ import annotations

import pytest

from aws.lambdas import cleanup


class FakeIoT:
    def __init__(self, *, shared: bool = False):
        self.shared = shared
        self.calls: list[tuple[str, dict]] = []
        self.principal = "arn:aws:iot:ap-south-1:123456789012:cert/abc123"

    def list_things(self, **kwargs):
        self.calls.append(("list_things", kwargs))
        return {
            "things": [
                {
                    "thingName": "QM-session-1-SIM-0001",
                    "attributes": {"Project": "QuakeMesh", "SessionId": "session-1"},
                },
                {
                    "thingName": "UNRELATED",
                    "attributes": {"Project": "QuakeMesh", "SessionId": "session-1"},
                },
                {
                    "thingName": "QM-session-1-SIM-9999",
                    "attributes": {"Project": "Other", "SessionId": "session-1"},
                },
            ]
        }

    def list_thing_principals(self, **kwargs):
        self.calls.append(("list_thing_principals", kwargs))
        return {"principals": [self.principal]}

    def list_principal_things(self, **kwargs):
        self.calls.append(("list_principal_things", kwargs))
        things = ["QM-session-1-SIM-0001"]
        if self.shared:
            things.append("unrelated-device")
        return {"things": things}

    def list_attached_policies(self, **kwargs):
        self.calls.append(("list_attached_policies", kwargs))
        return {"policies": [{"policyName": "QuakeMeshV2-session-1-DevicePolicy"}]}

    def __getattr__(self, name):
        def record(**kwargs):
            self.calls.append((name, kwargs))
            return {}

        return record


class FakeSns:
    def __init__(self):
        self.deleted: list[str] = []

    def list_endpoints_by_platform_application(self, **kwargs):
        assert kwargs["PlatformApplicationArn"] == "arn:platform"
        return {
            "Endpoints": [
                {
                    "EndpointArn": "arn:owned",
                    "Attributes": {"CustomUserData": "QuakeMesh:session-1"},
                },
                {
                    "EndpointArn": "arn:other-session",
                    "Attributes": {"CustomUserData": "QuakeMesh:session-2"},
                },
                {"EndpointArn": "arn:unmarked", "Attributes": {}},
            ]
        }

    def delete_endpoint(self, **kwargs):
        self.deleted.append(kwargs["EndpointArn"])


def test_owned_things_requires_attribute_and_exact_name_prefix():
    iot = FakeIoT()
    assert cleanup.owned_things(iot, "session-1") == [
        {
            "thingName": "QM-session-1-SIM-0001",
            "attributes": {"Project": "QuakeMesh", "SessionId": "session-1"},
        }
    ]
    assert iot.calls[0][1]["attributeName"] == "SessionId"
    assert iot.calls[0][1]["attributeValue"] == "session-1"


def test_cleanup_removes_only_verified_unshared_thing_credentials():
    iot = FakeIoT()
    cleanup.delete_owned_thing(iot, "QM-session-1-SIM-0001", "QuakeMeshV2-session-1-DevicePolicy")
    names = [name for name, _ in iot.calls]
    assert names[-5:] == [
        "detach_policy",
        "detach_thing_principal",
        "update_certificate",
        "delete_certificate",
        "delete_thing",
    ]


def test_cleanup_refuses_shared_certificate_before_mutation():
    iot = FakeIoT(shared=True)
    with pytest.raises(RuntimeError, match="shared certificate"):
        cleanup.delete_owned_thing(
            iot, "QM-session-1-SIM-0001", "QuakeMeshV2-session-1-DevicePolicy"
        )
    assert not any(name.startswith("delete_") or name.startswith("detach_") for name, _ in iot.calls)


def test_cleanup_deletes_only_exact_session_sns_endpoints():
    sns = FakeSns()
    assert cleanup.delete_owned_endpoints(sns, "arn:platform", "session-1") == 1
    assert sns.deleted == ["arn:owned"]
