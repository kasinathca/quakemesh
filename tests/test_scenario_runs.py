from local_runtime.repository import SQLiteRepository
from local_runtime.scenarios import SCENARIOS, create_run, execute_run
from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import SyntheticGeoIndex
from quakemesh_core.models import TelemetryTrigger
from quakemesh_core.correlation import canonicalize_trigger

def test_scenario_run_and_stage_round_trip(tmp_path):
    repo=SQLiteRepository(tmp_path/"runs.db")
    run=create_run(repo,"isolated",5,17,source="test",parameters={"note":"deterministic"})
    assert run["status"]=="QUEUED" and run["expected_result"]=="NO_CONFIRMATION"
    assert run["parameters"]=={"note":"deterministic"} and run["stages"][0]["code"]=="RUN_REQUESTED"
    repo.update_scenario_run(run["run_id"],status="COMPLETED",observed_result="NO_CONFIRMATION",event_ids=[])
    updated=repo.get_scenario_run(run["run_id"])
    assert updated["status"]=="COMPLETED" and updated["observed_result"]=="NO_CONFIRMATION"

def test_required_scenario_catalog_is_present():
    assert {"isolated","same-cell","distributed","degraded"} <= set(SCENARIOS)

def test_scenario_run_rejects_unsafe_inputs(tmp_path):
    repo=SQLiteRepository(tmp_path/"runs.db")
    for args in (("unknown",5,1),("isolated",0,1),("isolated",501,1)):
        try:create_run(repo,*args,source="test")
        except ValueError:pass
        else:raise AssertionError(f"accepted invalid scenario arguments: {args}")

def test_scenario_evidence_is_isolated_from_physical_evidence(tmp_path):
    repo=SQLiteRepository(tmp_path/"runs.db");cfg=DetectionConfig(h3_device_resolution=7,h3_correlation_resolution=7)
    trigger=TelemetryTrigger("1.0","dev-a",1,1000,12,77,1.2,2.2,"test")
    evidence=canonicalize_trigger(trigger,SyntheticGeoIndex(),cfg)
    assert repo.add_evidence(evidence,scenario_run_id="run-a")
    assert repo.recent_evidence(0)==[]
    assert [item.evidence_id for item in repo.recent_evidence(0,"run-a")]==[evidence.evidence_id]

def test_execute_run_handles_trace_rows_without_results(tmp_path,monkeypatch):
    repo=SQLiteRepository(tmp_path/"runs.db");run=create_run(repo,"degraded",5,42,source="test")
    class FakeTransport:
        def __init__(self,*args,**kwargs):pass
        def close(self):pass
    def fake_scenario(self,name):
        self.trace=[{"kind":"trigger_dropped_by_simulator","result":None,"error":None}]
    monkeypatch.setattr("local_runtime.scenarios.HttpTransport",FakeTransport)
    monkeypatch.setattr("local_runtime.scenarios.Fleet.scenario",fake_scenario)
    execute_run(repo,run["run_id"],"http://127.0.0.1:1")
    finished=repo.get_scenario_run(run["run_id"])
    assert finished["status"]=="COMPLETED" and finished["observed_result"]=="NO_CONFIRMATION"
