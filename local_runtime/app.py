from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import BackgroundTasks, FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from quakemesh_core.config import DetectionConfig
from quakemesh_core.geo import H3GeoIndex, SyntheticGeoIndex
from quakemesh_core.timeutil import now_ms
from quakemesh_core.validation import ValidationError

from .contracts import AlertAcknowledgementRequest, ScenarioRunRequest, V2Envelope
from .errors import ApiError
from .repository import ActiveScenarioRunError, SQLiteRepository
from .scenarios import API_SCHEMA_VERSION, APPLICATION_VERSION, ScenarioControlService
from .service import QuakeMeshService


@dataclass
class RuntimeContainer:
    application: QuakeMeshService
    scenarios: ScenarioControlService


def build_runtime() -> RuntimeContainer:
    root = Path(__file__).resolve().parents[1]
    database_path = os.getenv("QM_LOCAL_DB", str(root / "artifacts" / "quakemesh.db"))
    adapter = os.getenv("QM_GEO_ADAPTER", "h3").lower()
    if adapter == "synthetic":
        if os.getenv("QM_ALLOW_SYNTHETIC_GEO") != "1":
            raise RuntimeError(
                "Synthetic geo is test-only; set QM_ALLOW_SYNTHETIC_GEO=1 explicitly"
            )
        geo = SyntheticGeoIndex()
    else:
        geo = H3GeoIndex()
    repository = SQLiteRepository(database_path)
    config = DetectionConfig.from_env()
    application = QuakeMeshService(repository, geo, config)
    scenarios = ScenarioControlService(
        repository,
        config,
        root / "artifacts" / "session_exports" / "local",
    )
    return RuntimeContainer(application, scenarios)


app = FastAPI(title="QuakeMesh Local Runtime", version=APPLICATION_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Last-Event-ID", "X-QuakeMesh-Run-Id"],
    expose_headers=["X-Request-ID"],
)
_runtime: RuntimeContainer | None = None


def runtime() -> RuntimeContainer:
    global _runtime
    if _runtime is None:
        _runtime = build_runtime()
    return _runtime


def service() -> QuakeMeshService:
    return runtime().application


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid.uuid4()))


def _success(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    envelope = V2Envelope(request_id=_request_id(request), data=data)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def _error_content(request_id: str, error: ApiError) -> dict:
    return {
        "schema_version": API_SCHEMA_VERSION,
        "error": {
            "code": error.code,
            "message": error.message,
            "request_id": request_id,
            "details": error.details,
        },
    }


@app.middleware("http")
async def request_identity(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content=_error_content(_request_id(request), error),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "location": [str(value) for value in item["loc"]],
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]
    api_error = ApiError(422, "REQUEST_VALIDATION_FAILED", "Request validation failed.", {"errors": details})
    return JSONResponse(
        status_code=422,
        content=_error_content(_request_id(request), api_error),
    )


@app.exception_handler(ValidationError)
async def telemetry_validation_handler(request: Request, error: ValidationError) -> JSONResponse:
    api_error = ApiError(400, "TELEMETRY_VALIDATION_FAILED", str(error))
    return JSONResponse(
        status_code=400,
        content=_error_content(_request_id(request), api_error),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    # The exception is intentionally not serialized to avoid leaking local details.
    api_error = ApiError(500, "INTERNAL_ERROR", "The request could not be completed.")
    return JSONResponse(
        status_code=500,
        content=_error_content(_request_id(request), api_error),
    )


def _event_view(event) -> dict:
    result = event.as_dict()
    result["footprint_polygons"] = [
        {"cell": cell, "boundary": service().geo.boundary(cell)}
        for cell in event.detection_footprint
    ]
    result["frontier_polygons"] = [
        {"cell": cell, "boundary": service().geo.boundary(cell)}
        for cell in event.warning_frontier
    ]
    return result


def _require_loopback(request: Request) -> None:
    if request.client is None or request.client.host not in {
        "127.0.0.1",
        "::1",
        "testclient",
    }:
        raise ApiError(403, "LOCAL_CONTROL_FORBIDDEN", "Local demo control is loopback-only.")


@app.get("/health")
def health(request: Request) -> JSONResponse:
    return _success(
        request,
        {
            "status": "ok",
            "mode": "LOCAL",
            "application_version": APPLICATION_VERSION,
            "stats": service().repository.stats(),
        },
    )


@app.get("/v1/config")
def config(request: Request) -> JSONResponse:
    return _success(
        request,
        {
            "mode": "LOCAL",
            "application_version": APPLICATION_VERSION,
            "detector": asdict(service().config),
            "scenario_policy": {"maximum_active_runs": 1, "cancellation_supported": False},
        },
    )


@app.get("/v1/devices")
def devices(request: Request, limit: int = Query(200, ge=1, le=1_000)) -> JSONResponse:
    return _success(request, {"items": service().repository.list_devices(limit)})


@app.post("/v1/devices/heartbeat")
def heartbeat(
    payload: dict,
    request: Request,
    x_quakemesh_run_id: str | None = Header(default=None),
) -> JSONResponse:
    try:
        result = service().heartbeat(
            payload,
            "local-http",
            now_ms(),
            x_quakemesh_run_id,
        )
    except ValueError as error:
        raise ApiError(409, "SCENARIO_RUN_NOT_ACTIVE", str(error)) from error
    return _success(request, result)


@app.post("/v1/evidence/trigger")
def trigger(
    payload: dict,
    request: Request,
    x_quakemesh_run_id: str | None = Header(default=None),
) -> JSONResponse:
    try:
        result = service().trigger(
            payload,
            "local-http",
            now_ms(),
            x_quakemesh_run_id,
        )
    except ValueError as error:
        raise ApiError(409, "SCENARIO_RUN_NOT_ACTIVE", str(error)) from error
    return _success(request, result)


@app.get("/v1/events")
def events(request: Request, limit: int = Query(100, ge=1, le=500)) -> JSONResponse:
    return _success(
        request,
        {"items": [_event_view(event) for event in service().repository.list_events(limit)]},
    )


@app.get("/v1/events/{event_id}")
def event(event_id: str, request: Request) -> JSONResponse:
    found = service().repository.get_event(event_id)
    if found is None:
        raise ApiError(404, "EVENT_NOT_FOUND", "The requested event was not found.")
    return _success(request, _event_view(found))


@app.get("/v1/alerts")
def alerts(request: Request, limit: int = Query(200, ge=1, le=2_000)) -> JSONResponse:
    return _success(request, {"items": service().repository.list_alerts(limit)})


@app.post("/v1/alerts/{alert_id}/ack")
def acknowledge_alert(
    alert_id: str,
    payload: AlertAcknowledgementRequest,
    request: Request,
) -> JSONResponse:
    try:
        alert, changed = service().acknowledge_alert(
            alert_id,
            now_ms(),
            payload.acknowledgement_source,
            payload.device_id,
        )
    except ValueError as error:
        raise ApiError(409, "ALERT_DEVICE_MISMATCH", str(error)) from error
    if alert is None:
        raise ApiError(404, "ALERT_NOT_FOUND", "The requested alert was not found.")
    return _success(request, {"alert": alert, "transition_created": changed})


@app.get("/v1/scenarios")
def scenarios(request: Request) -> JSONResponse:
    return _success(request, {"items": runtime().scenarios.catalog()})


@app.get("/v1/scenario-runs")
def scenario_runs(request: Request, limit: int = Query(50, ge=1, le=200)) -> JSONResponse:
    return _success(request, {"items": service().repository.list_scenario_runs(limit)})


@app.get("/v1/scenario-runs/{run_id}")
def scenario_run(run_id: str, request: Request) -> JSONResponse:
    found = service().repository.get_scenario_run(run_id)
    if found is None:
        raise ApiError(404, "SCENARIO_RUN_NOT_FOUND", "The scenario run was not found.")
    return _success(request, found)


@app.get("/v1/session")
def session(request: Request) -> JSONResponse:
    return _success(
        request,
        {
            "mode": "LOCAL",
            "active_run": service().repository.active_scenario_run(),
            "started_at_ms": None,
            "expires_at_ms": None,
        },
    )


@app.post("/v1/demo/scenario-runs")
def start_scenario(
    payload: ScenarioRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    _require_loopback(request)
    try:
        run = runtime().scenarios.start_run(
            payload.scenario,
            source=payload.source,
            devices=payload.devices,
            seed=payload.seed,
            parameters=payload.parameters,
        )
    except ActiveScenarioRunError as error:
        raise ApiError(
            409,
            "SCENARIO_ALREADY_RUNNING",
            "A scenario run is already active.",
            {"active_run_id": error.run_id},
        ) from error
    except ValueError as error:
        raise ApiError(400, "INVALID_SCENARIO_PARAMETERS", str(error)) from error
    background_tasks.add_task(
        runtime().scenarios.execute_run,
        run["run_id"],
        str(request.base_url).rstrip("/"),
    )
    return _success(request, run, 202)


@app.post("/v1/demo/reset")
def reset_demo(request: Request) -> JSONResponse:
    _require_loopback(request)
    try:
        counts = runtime().scenarios.reset()
    except ActiveScenarioRunError as error:
        raise ApiError(
            409,
            "SCENARIO_RESET_BLOCKED",
            "Scenario data cannot be reset while a run is active.",
            {"active_run_id": error.run_id},
        ) from error
    return _success(request, {"deleted": counts, "physical_records_preserved": True})


@app.post("/v1/demo/scenario-runs/{run_id}/export")
def export_scenario(run_id: str, request: Request) -> JSONResponse:
    _require_loopback(request)
    try:
        path = runtime().scenarios.export_run(run_id)
    except KeyError as error:
        raise ApiError(404, "SCENARIO_RUN_NOT_FOUND", "The scenario run was not found.") from error
    return _success(
        request,
        {"run_id": run_id, "format": "json", "path": str(path.resolve())},
    )


@app.post("/v1/admin/resolve-stale")
def resolve(request: Request) -> JSONResponse:
    return _success(request, {"resolved": service().resolve(now_ms())})


async def _telemetry_events(
    request: Request,
    after_stage_id: int,
) -> AsyncIterator[str]:
    cursor = after_stage_id
    while not await request.is_disconnected():
        stages = service().repository.list_stages_after(cursor)
        if stages:
            for stage in stages:
                cursor = int(stage["stage_id"])
                event = {
                    "schema_version": API_SCHEMA_VERSION,
                    "event_type": "scenario.stage",
                    "sequence": cursor,
                    "emitted_at_ms": now_ms(),
                    "data": stage,
                }
                yield f"id: {cursor}\nevent: scenario.stage\ndata: {json.dumps(event)}\n\n"
        else:
            yield ": keep-alive\n\n"
        await asyncio.sleep(1.0)


@app.get("/v1/telemetry/stream")
async def telemetry_stream(
    request: Request,
    after: int = Query(0, ge=0),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    cursor = after
    if last_event_id:
        try:
            cursor = max(cursor, int(last_event_id))
        except ValueError as error:
            raise ApiError(400, "INVALID_STREAM_CURSOR", "Last-Event-ID must be an integer.") from error
    return StreamingResponse(
        _telemetry_events(request, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
