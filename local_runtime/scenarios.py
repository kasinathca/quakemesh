from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from quakemesh_core.config import DetectionConfig
from quakemesh_core.timeutil import now_ms
from simulator.fleet import Fleet
from simulator.transports import HttpTransport, Transport

from .repository import SQLiteRepository
from .scenario_catalog import CATALOG_VERSION, SCENARIOS, catalog_items, normalize_parameters


API_SCHEMA_VERSION = "2.0"
APPLICATION_VERSION = "1.0.1"


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"QMR-{stamp}-{secrets.token_hex(2).upper()}"


class ScenarioControlService:
    """Authoritative state machine for every controlled local scenario."""

    def __init__(
        self,
        repository: SQLiteRepository,
        detector_config: DetectionConfig,
        export_root: str | Path,
        transport_factory: Callable[..., Transport] = HttpTransport,
    ):
        self.repository = repository
        self.detector_config = detector_config
        self.export_root = Path(export_root)
        self.transport_factory = transport_factory

    def catalog(self) -> list[dict[str, Any]]:
        return catalog_items()

    def start_run(
        self,
        scenario: str,
        *,
        source: str,
        devices: int | None = None,
        seed: int | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict:
        if source not in {"cli", "dashboard", "android", "test"}:
            raise ValueError("unsupported scenario source")
        effective = normalize_parameters(
            scenario,
            devices=devices,
            seed=seed,
            parameters=parameters,
        )
        created_at_ms = now_ms()
        run = {
            "run_id": new_run_id(),
            "scenario": scenario,
            "source": source,
            "mode": "local",
            "catalog_version": CATALOG_VERSION,
            "seed": int(effective["seed"]),
            "devices": int(effective["devices"]),
            "status": "QUEUED",
            "expected_result": SCENARIOS[scenario].expected_result,
            "observed_result": None,
            "created_at_ms": created_at_ms,
            "started_at_ms": None,
            "completed_at_ms": None,
            "parameters": effective,
            "event_ids": [],
            "error": None,
        }
        return self.repository.create_scenario_run(run)

    def execute_run(self, run_id: str, base_url: str) -> None:
        run = self.repository.get_scenario_run(run_id)
        if run is None:
            raise KeyError(run_id)
        started_at_ms = now_ms()
        if not self.repository.mark_scenario_running(run_id, started_at_ms):
            return
        self.repository.add_scenario_stage(
            run_id,
            now_ms(),
            "PREFLIGHT_COMPLETED",
            "scenario-control",
            "info",
            "Scenario parameters and local runtime target validated",
            {"mode": "local", "schema_version": API_SCHEMA_VERSION},
        )
        transport: Transport | None = None
        try:
            transport = self.transport_factory(base_url, run_id=run_id)
            fleet = Fleet(
                Fleet.around(
                    run["devices"],
                    12.9716,
                    77.5946,
                    device_prefix=f"QM-SIM-{run_id[-4:]}",
                ),
                transport,
                run["seed"],
            )
            self.repository.add_scenario_stage(
                run_id,
                now_ms(),
                "FLEET_PREPARED",
                "simulator",
                "info",
                f"Prepared {run['devices']} virtual devices",
                {"devices": run["devices"], "seed": run["seed"]},
            )
            fleet.heartbeat_all()
            heartbeat_errors = sum(
                1 for row in fleet.trace if row["kind"] == "heartbeat" and row.get("error")
            )
            self.repository.add_scenario_stage(
                run_id,
                now_ms(),
                "HEARTBEAT_GENERATED",
                "simulator",
                "warning" if heartbeat_errors else "info",
                "Virtual-phone heartbeats generated",
                {"count": run["devices"], "transport_errors": heartbeat_errors},
            )
            fleet.inject_scenario(run["scenario"], run["parameters"])
            errors = [row for row in fleet.trace if row.get("error")]
            event_ids = sorted(
                {
                    result["event"]["event_id"]
                    for row in fleet.trace
                    if (result := row.get("result") or {}).get("event")
                }
            )
            observed_result = "CONFIRMATION" if event_ids else "NO_CONFIRMATION"
            expected_result = run["expected_result"]
            expectation_met = (
                expected_result == "CONDITIONAL" or expected_result == observed_result
            )
            completed_at_ms = now_ms()
            status = "COMPLETED" if not errors else "FAILED"
            self.repository.add_scenario_stage(
                run_id,
                completed_at_ms,
                "RUN_EVALUATED",
                "scenario-control",
                "info" if expectation_met and not errors else "error",
                "Observed scenario result evaluated against the catalog expectation",
                {
                    "expected_result": expected_result,
                    "observed_result": observed_result,
                    "expectation_met": expectation_met,
                    "event_ids": event_ids,
                    "transport_errors": len(errors),
                },
            )
            self.repository.update_scenario_run(
                run_id,
                status=status,
                observed_result=observed_result,
                completed_at_ms=completed_at_ms,
                event_ids=event_ids,
                error=None if not errors else f"{len(errors)} transport error(s)",
            )
            self.repository.add_scenario_stage(
                run_id,
                completed_at_ms,
                "RUN_COMPLETED" if status == "COMPLETED" else "RUN_FAILED",
                "scenario-control",
                "info" if status == "COMPLETED" and expectation_met else "error",
                f"Scenario finished with {observed_result}",
                {"expectation_met": expectation_met, "transport_errors": len(errors)},
            )
        except Exception as exc:
            completed_at_ms = now_ms()
            safe_error = f"{type(exc).__name__}: {str(exc)[:400]}"
            self.repository.update_scenario_run(
                run_id,
                status="FAILED",
                completed_at_ms=completed_at_ms,
                error=safe_error,
            )
            self.repository.add_scenario_stage(
                run_id,
                completed_at_ms,
                "RUN_FAILED",
                "scenario-control",
                "error",
                "Scenario execution failed",
                {"error_type": type(exc).__name__},
            )
        finally:
            if transport is not None:
                transport.close()

    def reset(self) -> dict[str, int]:
        return self.repository.reset_scenario_data()

    def export_run(self, run_id: str) -> Path:
        run = self.repository.get_scenario_run(run_id)
        if run is None:
            raise KeyError(run_id)
        events = [event.as_dict() for event in self.repository.list_events(500, run_id)]
        alerts = self.repository.list_alerts(2_000, run_id)
        safe_alerts = [
            {
                key: value
                for key, value in alert.items()
                if key not in {"fcm_token"}
            }
            for alert in alerts
        ]
        payload = {
            "schema_version": API_SCHEMA_VERSION,
            "exported_at_ms": now_ms(),
            "application_version": APPLICATION_VERSION,
            "detector_configuration": asdict(self.detector_config),
            "run": run,
            "events": events,
            "alerts": safe_alerts,
        }
        destination = self.export_root / run_id
        destination.mkdir(parents=True, exist_ok=True)
        output = destination / "run-evidence.json"
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return output


def create_run(
    repository: SQLiteRepository,
    scenario: str,
    devices: int,
    seed: int,
    source: str = "dashboard",
    parameters: dict[str, Any] | None = None,
) -> dict:
    service = ScenarioControlService(
        repository,
        DetectionConfig(),
        Path("artifacts/session_exports/local"),
    )
    return service.start_run(
        scenario,
        source=source,
        devices=devices,
        seed=seed,
        parameters=parameters,
    )


def execute_run(repository: SQLiteRepository, run_id: str, base_url: str) -> None:
    service = ScenarioControlService(
        repository,
        DetectionConfig(),
        Path("artifacts/session_exports/local"),
    )
    service.execute_run(run_id, base_url)
