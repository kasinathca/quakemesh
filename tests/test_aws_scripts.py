from __future__ import annotations

import json
from pathlib import Path

from aws.scripts import delete_devices, upload_trace


class FakeIoT:
    def __init__(self):
        self.calls=[]
        self.principal="arn:aws:iot:ap-south-1:123456789012:cert/abc123"
    def list_thing_principals(self, **kwargs):
        self.calls.append(("list_thing_principals", kwargs));return {"principals":[self.principal]}
    def list_attached_policies(self, **kwargs):
        self.calls.append(("list_attached_policies", kwargs));return {"policies":[{"policyName":"QuakeMeshDevicePolicy"}]}
    def detach_policy(self, **kwargs):self.calls.append(("detach_policy",kwargs))
    def detach_thing_principal(self, **kwargs):self.calls.append(("detach_thing_principal",kwargs))
    def update_certificate(self, **kwargs):self.calls.append(("update_certificate",kwargs))
    def delete_certificate(self, **kwargs):self.calls.append(("delete_certificate",kwargs))
    def delete_thing(self, **kwargs):self.calls.append(("delete_thing",kwargs))


def test_delete_thing_discovers_cloud_principal_and_removes_local_material(tmp_path: Path):
    thing="QM-SIM-0001";d=tmp_path/thing;d.mkdir();(d/"private.pem.key").write_text("secret")
    iot=FakeIoT()
    errors=delete_devices.delete_thing(iot,thing,tmp_path)
    assert errors==[]
    assert not d.exists()
    names=[name for name,_ in iot.calls]
    assert "detach_policy" in names
    assert "detach_thing_principal" in names
    assert "update_certificate" in names
    assert "delete_certificate" in names
    assert names[-1]=="delete_thing"


def test_delete_thing_dry_run_keeps_local_material(tmp_path: Path):
    thing="QM-SIM-0001";d=tmp_path/thing;d.mkdir();(d/"certificate-arn.txt").write_text("arn:aws:iot:x:y:cert/abc123")
    errors=delete_devices.delete_thing(FakeIoT(),thing,tmp_path,dry_run=True)
    assert errors==[] and d.exists()


def test_trace_validation_and_hash(tmp_path: Path):
    p=tmp_path/"trace.json";p.write_text(json.dumps({"trace_schema":"1.0","records":[]}))
    assert upload_trace.validate_trace(p)["trace_schema"]=="1.0"
    assert len(upload_trace.sha256_file(p))==64


def test_trace_validation_rejects_arbitrary_json(tmp_path: Path):
    p=tmp_path/"not-trace.json";p.write_text("{}")
    try:
        upload_trace.validate_trace(p)
    except ValueError as exc:
        assert "trace_schema" in str(exc)
    else:
        raise AssertionError("invalid trace accepted")
