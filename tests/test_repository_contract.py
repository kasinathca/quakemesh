import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_json_contracts_parse_and_are_v1():
    for p in (ROOT/"schemas").glob("*.json"):
        data=json.loads(p.read_text());assert "1.0" in (data.get("$id","")+json.dumps(data))

def test_iot_policy_is_thing_scoped():
    s=(ROOT/"aws/infrastructure/stack.py").read_text()
    assert '${iot:Connection.Thing.ThingName}' in s
    assert 'quakemesh/v1/devices/{thing_var}/trigger' in s
    assert 'quakemesh/v1/devices/{thing_var}/alerts' in s

def test_https_writes_require_api_key():
    s=(ROOT/"aws/infrastructure/stack.py").read_text()
    assert s.count('add_method("POST",integration,api_key_required=True)')==2

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
    assert '"-m", "ruff", "check"' in text
    assert '"src", "local_runtime", "simulator", "aws", "scripts", "tests"' in text
    assert 'ruff check .' not in text.lower()
    assert "$LASTEXITCODE -ne 0" in text
    assert "all gates passed" in text.lower()


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
