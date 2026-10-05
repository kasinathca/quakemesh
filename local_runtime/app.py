from __future__ import annotations

import os
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex, SyntheticGeoIndex
from quakemesh_core.timeutil import now_ms
from quakemesh_core.validation import ValidationError
from .repository import SQLiteRepository
from .service import QuakeMeshService
from .scenarios import SCENARIOS, create_run, execute_run


def build_service()->QuakeMeshService:
    db=os.getenv("QM_LOCAL_DB",str(Path(__file__).resolve().parents[1]/"artifacts"/"quakemesh.db"))
    adapter=os.getenv("QM_GEO_ADAPTER","h3").lower()
    if adapter=="synthetic":
        if os.getenv("QM_ALLOW_SYNTHETIC_GEO")!="1": raise RuntimeError("Synthetic geo is test-only; set QM_ALLOW_SYNTHETIC_GEO=1 explicitly")
        geo=SyntheticGeoIndex()
    else: geo=H3GeoIndex()
    return QuakeMeshService(SQLiteRepository(db),geo,DetectionConfig.from_env())

app=FastAPI(title="QuakeMesh Local Runtime",version="1.0.1")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:8080","http://127.0.0.1:8080"],allow_credentials=False,allow_methods=["GET","POST"],allow_headers=["Content-Type"])
_service:QuakeMeshService|None=None

def service()->QuakeMeshService:
    global _service
    if _service is None: _service=build_service()
    return _service

@app.get("/health")
def health(): return {"status":"ok","mode":"local","stats":service().repo.stats()}

@app.post("/v1/devices/heartbeat")
def heartbeat(payload:dict):
    try: return service().heartbeat(payload,"local-http",now_ms())
    except ValidationError as e: raise HTTPException(400,str(e))

@app.post("/v1/evidence/trigger")
def trigger(payload:dict,x_quakemesh_run_id:str|None=Header(default=None)):
    try: return service().trigger(payload,"local-http",now_ms(),x_quakemesh_run_id)
    except ValidationError as e: raise HTTPException(400,str(e))

def _event_view(e):
    out=e.as_dict()
    out["footprint_polygons"]=[{"cell":c,"boundary":service().geo.boundary(c)} for c in e.detection_footprint]
    out["frontier_polygons"]=[{"cell":c,"boundary":service().geo.boundary(c)} for c in e.warning_frontier]
    return out

@app.get("/v1/events")
def events(limit:int=100): return {"items":[_event_view(e) for e in service().repo.list_events(min(max(limit,1),500))]}

@app.get("/v1/events/{event_id}")
def event(event_id:str):
    e=service().repo.get_event(event_id)
    if not e: raise HTTPException(404,"event not found")
    return _event_view(e)

@app.get("/v1/alerts")
def alerts(limit:int=200): return {"items":service().repo.list_alerts(min(max(limit,1),1000))}

@app.get("/v1/scenarios")
def scenarios(): return {"items":[{"id":name,**definition} for name,definition in SCENARIOS.items()]}

@app.get("/v1/scenario-runs")
def scenario_runs(limit:int=50): return {"items":service().repo.list_scenario_runs(min(max(limit,1),200))}

@app.get("/v1/scenario-runs/{run_id}")
def scenario_run(run_id:str):
    run=service().repo.get_scenario_run(run_id)
    if not run:raise HTTPException(404,"scenario run not found")
    return run

@app.post("/v1/demo/scenario-runs",status_code=202)
def start_scenario(payload:dict,request:Request,background_tasks:BackgroundTasks):
    if request.client is None or request.client.host not in {"127.0.0.1","::1","testclient"}:
        raise HTTPException(403,"local demo control is loopback-only")
    try:
        run=create_run(service().repo,str(payload.get("scenario","")),int(payload.get("devices",25)),int(payload.get("seed",42)),str(payload.get("source","dashboard")),payload.get("parameters") or {})
    except (TypeError,ValueError) as exc:raise HTTPException(400,str(exc))
    background_tasks.add_task(execute_run,service().repo,run["run_id"],str(request.base_url).rstrip("/"))
    return run

@app.post("/v1/admin/resolve-stale")
def resolve(): return {"resolved":service().resolve(now_ms())}

@app.websocket("/ws")
async def ws(websocket:WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type":"snapshot","ts":now_ms(),"events":[e.as_dict() for e in service().repo.list_events(25)],"stats":service().repo.stats()})
            import asyncio; await asyncio.sleep(2)
    except WebSocketDisconnect: return
