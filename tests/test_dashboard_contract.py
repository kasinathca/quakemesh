from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def dashboard_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "dashboard" / "src").rglob("*.tsx")
    ) + (ROOT / "dashboard" / "src" / "api" / "client.ts").read_text(encoding="utf-8")


def test_dashboard_scenario_lab_uses_authoritative_run_api():
    source = dashboard_source()
    assert "Scenario Lab" in source
    assert 'request<ScenarioRun>("/v1/demo/scenario-runs"' in source
    assert "/v1/scenario-runs/${encodeURIComponent(runId)}" in source
    assert "DEVICE_DIVERSITY_GATE_EVALUATED" in source
    assert "SPATIAL_DIVERSITY_GATE_EVALUATED" in source


def test_dashboard_has_truthful_scope_and_accessible_status_regions():
    source = dashboard_source()
    assert "Not an official warning system" in source
    assert 'role="alert"' in source
    assert 'role="status"' in source
    assert "Waiting for data" in source
