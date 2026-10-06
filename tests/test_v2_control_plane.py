from __future__ import annotations

import importlib
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from local_runtime.app import RuntimeContainer
from local_runtime.repository import ActiveScenarioRunError, SQLiteRepository
from local_runtime.scenarios import ScenarioControlService
from local_runtime.service import QuakeMeshService
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import SyntheticGeoIndex
from simulator.fleet import Fleet


class DirectTransport:
    def __init__(self, application: QuakeMeshService, run_id: str | None):
        self.application = application
        self.run_id = run_id

    def heartbeat(self, device_id: str, payload: dict) -> dict:
        return self.application.heartbeat(payload, "test-direct", run_id=self.run_id)

    def trigger(self, device_id: str, payload: dict) -> dict:
        return self.application.trigger(payload, "test-direct", run_id=self.run_id)

    def close(self) -> None:
        return None


class CaptureTransport:
    def __init__(self):
        self.triggers: list[dict] = []

    def heartbeat(self, device_id: str, payload: dict) -> dict:
        return {"accepted": True}

    def trigger(self, device_id: str, payload: dict) -> dict:
        self.triggers.append(payload)
        return {"accepted": True}

    def close(self) -> None:
        return None


def make_runtime(tmp_path) -> RuntimeContainer:
    repository = SQLiteRepository(tmp_path / "control.db")
    config = DetectionConfig(
        h3_device_resolution=7,
        h3_correlation_resolution=7,
        min_devices=4,
        min_distinct_cells=3,
    )
    application = QuakeMeshService(repository, SyntheticGeoIndex(), config)

    def factory(base_url: str, run_id: str | None = None) -> DirectTransport:
        return DirectTransport(application, run_id)

    scenarios = ScenarioControlService(
        repository,
        config,
        tmp_path / "exports",
        transport_factory=factory,
    )
    return RuntimeContainer(application, scenarios)


def execute(runtime: RuntimeContainer, scenario: str, source: str = "test") -> dict:
    run = runtime.scenarios.start_run(scenario, source=source)
    runtime.scenarios.execute_run(run["run_id"], "direct://test")
    return runtime.application.repository.get_scenario_run(run["run_id"])


def test_dashboard_and_cli_sources_share_equivalent_authoritative_records(tmp_path):
    runtime = make_runtime(tmp_path)
    dashboard = execute(runtime, "isolated", "dashboard")
    cli = execute(runtime, "isolated", "cli")
    assert dashboard["source"] == "dashboard"
    assert cli["source"] == "cli"
    for field in ("scenario", "mode", "catalog_version", "parameters", "expected_result"):
        assert dashboard[field] == cli[field]
    assert dashboard["run_id"] != cli["run_id"]


def test_atomic_single_active_run_policy(tmp_path):
    runtime = make_runtime(tmp_path)

    def start() -> str:
        return runtime.scenarios.start_run("isolated", source="test")["run_id"]

    outcomes: list[str] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start) for _ in range(2)]
        for future in futures:
            try:
                outcomes.append(future.result())
            except ActiveScenarioRunError as error:
                errors.append(error.run_id)
    assert len(outcomes) == 1
    assert errors == outcomes


def test_negative_scenarios_emit_truthful_failed_gates_only(tmp_path):
    runtime = make_runtime(tmp_path)
    isolated = execute(runtime, "isolated")
    isolated_codes = [stage["code"] for stage in isolated["stages"]]
    assert isolated["observed_result"] == "NO_CONFIRMATION"
    assert any(
        stage["code"] == "DEVICE_DIVERSITY_GATE_EVALUATED"
        and stage["status"] == "FAILED"
        for stage in isolated["stages"]
    )
    assert "EVENT_TRANSITIONED" not in isolated_codes
    assert "ALERT_RECORDED" not in isolated_codes

    same_cell = execute(runtime, "same-cell")
    same_cell_codes = [stage["code"] for stage in same_cell["stages"]]
    assert same_cell["observed_result"] == "NO_CONFIRMATION"
    assert any(
        stage["code"] == "SPATIAL_DIVERSITY_GATE_EVALUATED"
        and stage["status"] == "FAILED"
        for stage in same_cell["stages"]
    )
    assert "EVENT_TRANSITIONED" not in same_cell_codes


def test_scenario_and_physical_evidence_never_cross_merge(tmp_path):
    runtime = make_runtime(tmp_path)
    first = execute(runtime, "distributed")
    second = execute(runtime, "distributed")
    repository = runtime.application.repository
    first_events = repository.list_events(100, first["run_id"])
    second_events = repository.list_events(100, second["run_id"])
    assert len(first_events) == 1
    assert len(second_events) == 1
    assert first_events[0].event_id != second_events[0].event_id
    assert first_events[0].scenario_run_id == first["run_id"]
    assert second_events[0].scenario_run_id == second["run_id"]

    physical_fleet = Fleet(
        Fleet.around(8, 12.9716, 77.5946, device_prefix="QM-PHYSICAL-LIKE"),
        DirectTransport(runtime.application, None),
        seed=42,
    )
    physical_fleet.scenario("distributed")
    physical_events = [
        event for event in repository.list_events(100) if event.provenance_type == "physical"
    ]
    assert len(physical_events) == 1
    assert physical_events[0].scenario_run_id is None
    assert physical_events[0].event_id not in {
        first_events[0].event_id,
        second_events[0].event_id,
    }


def test_distributed_alert_ack_export_and_reset_are_truthful(tmp_path):
    runtime = make_runtime(tmp_path)
    run = execute(runtime, "distributed")
    repository = runtime.application.repository
    events = repository.list_events(100, run["run_id"])
    alerts = repository.list_alerts(1_000, run["run_id"])
    assert run["observed_result"] == "CONFIRMATION"
    assert events and alerts
    assert {alert["status"] for alert in alerts} == {"TARGETED"}
    assert {alert["scenario_run_id"] for alert in alerts} == {run["run_id"]}

    alert_id = alerts[0]["alert_id"]
    first, changed = runtime.application.acknowledge_alert(
        alert_id, 10_000, "test", alerts[0]["device_id"]
    )
    second, changed_again = runtime.application.acknowledge_alert(
        alert_id, 20_000, "test", alerts[0]["device_id"]
    )
    assert changed is True and changed_again is False
    assert first["acknowledged_at_ms"] == second["acknowledged_at_ms"] == 10_000
    ack_stages = [
        stage for stage in repository.get_scenario_run(run["run_id"])["stages"]
        if stage["code"] == "ALERT_ACKNOWLEDGED"
    ]
    assert len(ack_stages) == 1

    export_path = runtime.scenarios.export_run(run["run_id"])
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "2.0"
    assert exported["run"]["parameters"] == run["parameters"]
    serialized = export_path.read_text(encoding="utf-8").lower()
    assert "fcm_token" not in serialized
    assert "latitude" not in serialized
    assert "longitude" not in serialized

    physical_fleet = Fleet(
        Fleet.around(1, 12.9716, 77.5946, device_prefix="QM-PHYSICAL-PRESERVE"),
        DirectTransport(runtime.application, None),
    )
    physical_fleet.heartbeat_all()
    deleted = runtime.scenarios.reset()
    assert deleted["scenario_runs"] >= 1
    devices = repository.list_devices()
    assert [device["device_id"] for device in devices] == ["QM-PHYSICAL-PRESERVE-0001"]


def test_v2_api_envelopes_errors_and_complete_local_surface(tmp_path, monkeypatch):
    runtime = make_runtime(tmp_path)
    runtime_app = importlib.import_module("local_runtime.app")
    monkeypatch.setattr(runtime_app, "_runtime", runtime)
    client = TestClient(runtime_app.app, raise_server_exceptions=False)

    for path in (
        "/health",
        "/v1/config",
        "/v1/devices",
        "/v1/events",
        "/v1/alerts",
        "/v1/scenarios",
        "/v1/scenario-runs",
        "/v1/session",
    ):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["schema_version"] == "2.0"
        assert response.json()["request_id"]

    invalid = client.post(
        "/v1/demo/scenario-runs",
        json={"scenario": "isolated", "parameters": {"ignored": True}},
    )
    assert invalid.status_code == 400
    body = invalid.json()
    assert body["schema_version"] == "2.0"
    assert body["error"]["code"] == "INVALID_SCENARIO_PARAMETERS"
    assert body["error"]["request_id"]

    active = runtime.scenarios.start_run("isolated", source="test")
    blocked = client.post("/v1/demo/scenario-runs", json={"scenario": "isolated"})
    assert blocked.status_code == 409
    assert blocked.json()["error"] == {
        "code": "SCENARIO_ALREADY_RUNNING",
        "message": "A scenario run is already active.",
        "request_id": blocked.json()["error"]["request_id"],
        "details": {"active_run_id": active["run_id"]},
    }
    reset = client.post("/v1/demo/reset")
    assert reset.status_code == 409
    assert reset.json()["error"]["code"] == "SCENARIO_RESET_BLOCKED"


def test_stage_stream_sequence_is_monotonic_and_resumeable(tmp_path):
    runtime = make_runtime(tmp_path)
    run = execute(runtime, "distributed")
    stages = runtime.application.repository.list_stages_after(0)
    stage_ids = [stage["stage_id"] for stage in stages]
    assert stage_ids == sorted(stage_ids)
    assert len(stage_ids) == len(set(stage_ids))
    resumed = runtime.application.repository.list_stages_after(stage_ids[-3])
    assert [stage["stage_id"] for stage in resumed] == stage_ids[-2:]
    sequences = [stage["sequence"] for stage in run["stages"]]
    assert sequences == list(range(1, len(sequences) + 1))


def test_degraded_parameters_are_applied_deterministically():
    parameters = {
        "devices": 25,
        "seed": 91,
        "packet_loss_fraction": 0.5,
        "network_jitter_ms": 0,
        "trigger_propagation_interval_ms": 125,
    }
    outcomes = []
    for _ in range(2):
        transport = CaptureTransport()
        fleet = Fleet(Fleet.around(25, 12.0, 77.0), transport, seed=91)
        fleet.inject_scenario("degraded", parameters)
        observed = [payload["observed_at_ms"] for payload in transport.triggers]
        outcomes.append(
            {
                "drops": [
                    row["device_id"]
                    for row in fleet.trace
                    if row["kind"] == "trigger_dropped_by_simulator"
                ],
                "timestamps": [timestamp - observed[0] for timestamp in observed],
            }
        )
    assert outcomes[0] == outcomes[1]
    assert outcomes[0]["drops"]
    timestamps = outcomes[0]["timestamps"]
    assert all((right - left) % 125 == 0 for left, right in zip(timestamps, timestamps[1:]))
