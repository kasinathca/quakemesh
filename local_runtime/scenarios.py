from __future__ import annotations

from datetime import datetime, timezone
import secrets
from typing import Any

from quakemesh_core.timeutil import now_ms
from simulator.fleet import Fleet
from simulator.transports import HttpTransport

SCENARIOS: dict[str, dict[str, str]] = {
    "isolated": {"expected_result": "NO_CONFIRMATION", "purpose": "single-device false-positive suppression"},
    "same-cell": {"expected_result": "NO_CONFIRMATION", "purpose": "spatial-diversity rejection"},
    "distributed": {"expected_result": "CONFIRMATION", "purpose": "geographically diverse corroboration"},
    "degraded": {"expected_result": "CONDITIONAL", "purpose": "deterministic packet-loss and jitter evaluation"},
}

def new_run_id() -> str:
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"QMR-{stamp}-{secrets.token_hex(2).upper()}"

def create_run(repo, scenario: str, devices: int, seed: int, source: str="dashboard", parameters: dict[str,Any]|None=None) -> dict:
    if scenario not in SCENARIOS:raise ValueError("unknown scenario")
    if devices < 1 or devices > 500:raise ValueError("devices must be between 1 and 500")
    if source not in {"cli","dashboard","android","test"}:raise ValueError("unsupported scenario source")
    created=now_ms();run={"run_id":new_run_id(),"scenario":scenario,"source":source,"mode":"local","seed":seed,"devices":devices,
        "status":"QUEUED","expected_result":SCENARIOS[scenario]["expected_result"],"observed_result":None,"created_at_ms":created,
        "started_at_ms":None,"completed_at_ms":None,"parameters":parameters or {},"event_ids":[],"error":None}
    repo.create_scenario_run(run)
    repo.add_scenario_stage(run["run_id"],created,"RUN_REQUESTED","scenario-control","info",f"Scenario {scenario} requested",{"source":source,"devices":devices,"seed":seed})
    return repo.get_scenario_run(run["run_id"])

def execute_run(repo, run_id: str, base_url: str) -> None:
    run=repo.get_scenario_run(run_id)
    if not run:raise KeyError(run_id)
    started=now_ms();repo.update_scenario_run(run_id,status="RUNNING",started_at_ms=started)
    repo.add_scenario_stage(run_id,started,"FLEET_PREPARED","simulator","info",f"Prepared {run['devices']} virtual devices",{"devices":run["devices"]})
    transport=HttpTransport(base_url,run_id=run_id)
    fleet=Fleet(Fleet.around(run["devices"],12.9716,77.5946,device_prefix=f"QM-SIM-{run_id[-4:]}"),transport,run["seed"])
    try:
        repo.add_scenario_stage(run_id,now_ms(),"OBSERVATION_INJECTED","simulator","info","Scenario observation injection started",{"scenario":run["scenario"]})
        fleet.scenario(run["scenario"])
        errors=[row for row in fleet.trace if row.get("error")]
        event_ids=sorted({result["event"]["event_id"] for row in fleet.trace if (result := row.get("result") or {}).get("event")})
        observed="CONFIRMATION" if event_ids else "NO_CONFIRMATION";expected=run["expected_result"];met=expected=="CONDITIONAL" or expected==observed
        completed=now_ms();status="COMPLETED" if not errors else "FAILED"
        repo.update_scenario_run(run_id,status=status,observed_result=observed,completed_at_ms=completed,event_ids=event_ids,error=None if not errors else f"{len(errors)} transport error(s)")
        repo.add_scenario_stage(run_id,completed,"RUN_COMPLETED" if status=="COMPLETED" else "RUN_FAILED","scenario-control","info" if status=="COMPLETED" and met else "error",f"Scenario finished with {observed}",{"expected_result":expected,"expectation_met":met,"event_ids":event_ids,"transport_errors":len(errors)})
    except Exception as exc:
        completed=now_ms();repo.update_scenario_run(run_id,status="FAILED",completed_at_ms=completed,error=str(exc))
        repo.add_scenario_stage(run_id,completed,"RUN_FAILED","scenario-control","error","Scenario execution failed",{"error_type":type(exc).__name__})
    finally:transport.close()
