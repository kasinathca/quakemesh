from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_scenario_lab_uses_authoritative_run_api():
    html=(ROOT/"dashboard/index.html").read_text(encoding="utf-8")
    js=(ROOT/"dashboard/app.js").read_text(encoding="utf-8")
    assert 'id="scenarioForm"' in html and 'id="timeline"' in html and 'id="gateList"' in html
    assert 'post("/v1/demo/scenario-runs"' in js
    assert '/v1/scenario-runs/${encodeURIComponent(activeRunId)}' in js
    assert 'CORRELATION_EVALUATED' in js

def test_dashboard_has_truthful_scope_and_accessible_status_regions():
    html=(ROOT/"dashboard/index.html").read_text(encoding="utf-8")
    assert "not an official earthquake warning" in html
    assert 'aria-live="polite"' in html and 'role="alert"' in html
