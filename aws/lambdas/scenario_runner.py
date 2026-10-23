from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from boto3.dynamodb.conditions import Attr

from .common import boto3, env, log, now_ms
from .ingress import geo, process

ddb = boto3.resource("dynamodb")


def _table(name: str):
    return ddb.Table(env(name))


def _update(run_id: str, **values) -> None:
    names = {f"#k{i}": key for i, key in enumerate(values)}
    expression_values = {
        f":v{i}": Decimal(str(value)) if isinstance(value, float) else value
        for i, value in enumerate(values.values())
    }
    _table("QM_SCENARIO_TABLE").update_item(
        Key={"run_id": run_id},
        UpdateExpression="SET " + ",".join(f"{name}=:v{i}" for i, name in enumerate(names)),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=expression_values,
    )


def _positions(count: int, latitude: float, longitude: float, spacing: float = 0.012) -> list[tuple[float, float]]:
    side = max(1, int(count**0.5 + 0.999))
    return [
        (
            latitude + (index // side - (side - 1) / 2) * spacing,
            longitude + (index % side - (side - 1) / 2) * spacing,
        )
        for index in range(count)
    ]


def _event_for_run(run_id: str) -> dict | None:
    response = _table("QM_EVENT_TABLE").scan(
        ConsistentRead=True,
        FilterExpression=Attr("scenario_run_id").eq(run_id) & Attr("status").eq("CONFIRMED"),
    )
    return next(iter(response.get("Items", [])), None)


def handler(event, context):
    run_id = str(event["run_id"])
    table = _table("QM_SCENARIO_TABLE")
    run = table.get_item(Key={"run_id": run_id}, ConsistentRead=True).get("Item")
    if not run:
        return {"run_id": run_id, "status": "NOT_FOUND"}
    started = now_ms()
    _update(run_id, status="RUNNING", started_at_ms=started, updated_at_ms=started)
    try:
        scenario = str(run["scenario"])
        parameters = dict(run.get("parameters", {}))
        devices = int(parameters.get("devices", 25))
        rng = random.Random(int(parameters.get("seed", 42)))
        center_lat, center_lon = geo().center(str(run["reference_h3_cell"]))
        positions = _positions(devices, center_lat, center_lon)
        prefix = f"QM-{env('QM_SESSION_ID')}-VIRTUAL-{run_id[-8:]}"
        timestamp = now_ms()
        for index, (latitude, longitude) in enumerate(positions):
            process(
                {
                    "schema_version": "1.0", "device_id": f"{prefix}-{index + 1:04d}",
                    "seq": 1, "observed_at_ms": timestamp,
                    "latitude": latitude, "longitude": longitude,
                },
                "heartbeat", transport="scenario-runner", provenance_type="scenario",
                scenario_run_id=run_id, request=run_id,
            )

        if scenario == "isolated":
            trigger_indices = [0]
        elif scenario == "same-cell":
            trigger_indices = list(range(min(6, devices)))
            positions = [positions[0] for _ in positions]
        elif scenario in {"distributed", "false-positive"}:
            trigger_indices = list(range(min(8, devices)))
        elif scenario == "degraded":
            trigger_indices = list(range(min(16, devices)))
        else:
            raise ValueError("unknown scenario")

        loss = float(parameters.get("packet_loss_fraction", 0.25)) if scenario == "degraded" else 0.0
        interval = int(parameters.get("trigger_propagation_interval_ms", 70))
        jitter = int(parameters.get("network_jitter_ms", 0)) if scenario == "degraded" else 0
        trigger_jobs = []
        for ordinal, index in enumerate(trigger_indices):
            if rng.random() < loss:
                continue
            latitude, longitude = positions[index]
            below_gate = scenario == "false-positive"
            trigger_jobs.append((
                rng.randint(0, jitter) if jitter else 0,
                {
                    "schema_version": "1.0", "device_id": f"{prefix}-{index + 1:04d}",
                    "seq": 2, "observed_at_ms": timestamp + ordinal * interval,
                    "latitude": latitude, "longitude": longitude,
                    "motion_rms": 0.12 if below_gate else round(rng.uniform(1.0, 1.8), 4),
                    "motion_peak": 0.35 if below_gate else round(rng.uniform(2.0, 3.2), 4),
                },
            ))

        def deliver(job) -> bool:
            delay_ms, payload = job
            if delay_ms:
                time.sleep(delay_ms / 1000)
            result = process(
                payload, "trigger", transport="scenario-runner", provenance_type="scenario",
                scenario_run_id=run_id, request=run_id,
            )
            return bool(result.get("accepted"))

        with ThreadPoolExecutor(max_workers=min(16, max(1, len(trigger_jobs)))) as pool:
            delivered = sum(pool.map(deliver, trigger_jobs))

        expected = str(run["expected_result"])
        confirmed = None
        if expected in {"CONFIRMATION", "CONDITIONAL"}:
            deadline = time.time() + 24
            while time.time() < deadline:
                confirmed = _event_for_run(run_id)
                if confirmed:
                    break
                time.sleep(1)
        else:
            time.sleep(4)
            confirmed = _event_for_run(run_id)
        observed = "CONFIRMATION" if confirmed else "NO_CONFIRMATION"
        completed = now_ms()
        _update(
            run_id, status="COMPLETED", observed_result=observed,
            completed_at_ms=completed, updated_at_ms=completed,
            accepted_evidence=delivered,
            event_ids=[str(confirmed["event_id"])] if confirmed else [],
        )
        log("SCENARIO_RUN_COMPLETED", run_id, scenario=scenario, observed_result=observed)
        return {"run_id": run_id, "status": "COMPLETED", "observed_result": observed}
    except Exception as exc:
        completed = now_ms()
        _update(run_id, status="FAILED", completed_at_ms=completed, updated_at_ms=completed, error=f"{type(exc).__name__}: {exc}")
        log("SCENARIO_RUN_FAILED", run_id, error_type=type(exc).__name__, error_message=str(exc))
        raise
    finally:
        try:
            table.delete_item(Key={"run_id": "ACTIVE"}, ConditionExpression="active_run_id=:run", ExpressionAttributeValues={":run": run_id})
        except Exception:
            pass
