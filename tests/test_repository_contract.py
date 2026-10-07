import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_json_contracts_parse_and_use_explicit_versions():
    for p in (ROOT/"schemas").glob("*.json"):
        data=json.loads(p.read_text())
        serialized=data.get("$id","")+json.dumps(data)
        expected="2.0" if p.name.startswith("v2-") else "1.0"
        assert expected in serialized

def test_iot_policy_is_thing_scoped():
    s=(ROOT/"aws/infrastructure/stack.py").read_text()
    assert '${iot:Connection.Thing.ThingName}' in s
    assert 'topic_root = f"quakemesh/v1/{session_id}/devices"' in s
    assert 'resource_name=f"{topic_root}/{thing_var}/trigger"' in s
    assert 'resource_name=f"{topic_root}/{thing_var}/alerts"' in s

def test_https_writes_require_api_key():
    s=(ROOT/"aws/infrastructure/stack.py").read_text()
    assert s.count('api_key_required=True')==3

def test_aws_v2_stack_is_session_owned_and_destroyable():
    s=(ROOT/"aws/infrastructure/stack.py").read_text()
    for value in ['"SessionId": session_id', '"ExpiresAt": expires_at', '"Ephemeral": "true"']:
        assert value in s
    assert "RemovalPolicy.RETAIN" not in s
    assert s.count("removal_policy=RemovalPolicy.DESTROY") >= 6
    assert 'schedule_expression=f"at({expires_at.removesuffix(\'Z\')})"' in s
    assert '"cloudformation:DeleteStack"' in s
    assert '"iot:ListThings"' in s

def test_aws_v2_api_and_provenance_contracts_are_present():
    api=(ROOT/"aws/lambdas/api.py").read_text()
    ingress=(ROOT/"aws/lambdas/ingress.py").read_text()
    for endpoint in ["/health", "/v1/devices", "/v1/events", "/v1/alerts"]:
        assert endpoint in api
    assert "ALERT_DEVICE_MISMATCH" in api
    assert "X-QuakeMesh-Run-Id" in api
    assert 'provenance_type="scenario"' in ingress
    assert 'provenance_type:str="physical"' in ingress

def test_no_v1_vpc_compute_database_constructs():
    s=(ROOT/"aws/infrastructure/stack.py").read_text().lower()
    forbidden=["aws_ec2","aws_rds","aws_ecs","aws_eks","natgateway","vpc("]
    assert all(x not in s for x in forbidden)

def test_android_has_no_manual_confirmation_control():
    s=(ROOT/"android/app/src/main/java/com/quakemesh/app/MainActivity.kt").read_text().lower()
    assert "confirm earthquake" not in s and "simulate earthquake" not in s

def test_secret_paths_are_gitignored():
    s=(ROOT/".gitignore").read_text()
    for x in ["android/app/google-services.json","android/local.properties","artifacts/runtime-config.json","*.key"]:assert x in s


def test_windows_validator_scopes_ruff_and_checks_native_exit_codes():
    text = (ROOT / "scripts" / "validate.ps1").read_text(encoding="utf-8")
    assert "-m ruff check src local_runtime simulator aws scripts tests" in text
    assert "--select E4,E7,E9,F" in text
    assert 'ruff check .' not in text.lower()
    assert "$LASTEXITCODE -ne 0" in text
    assert "PASS, $script:Skipped SKIP, 0 FAIL" in text


def test_setup_checks_native_process_exit_codes():
    text = (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8")
    assert "$LASTEXITCODE -ne 0" in text
    assert "Invoke-Checked" in text


def test_dashboard_launcher_uses_named_parameter_splatting():
    demo = (ROOT / "scripts" / "demo_local.ps1").read_text(encoding="utf-8")
    helper = (ROOT / "scripts" / "process_helpers.ps1").read_text(encoding="utf-8")
    smoke = (ROOT / "scripts" / "test_process_helpers.ps1").read_text(encoding="utf-8")
    assert "-NamedArguments @{ Port = $DashboardPort }" in demo
    assert "@childParameters" in helper
    assert "'-Port'" not in helper
    assert "[int]$Port" in smoke and "8080" in smoke
