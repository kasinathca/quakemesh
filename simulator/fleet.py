from __future__ import annotations

import json
import math
import random
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .models import VirtualPhone
from .transports import Transport


class Fleet:
    def __init__(
        self,
        phones: list[VirtualPhone],
        transport: Transport,
        seed: int = 42,
        trace_path: str | Path | None = None,
    ):
        self.phones = phones
        self.transport = transport
        self.rng = random.Random(seed)
        self.trace: list[dict] = []
        self.trace_path = Path(trace_path) if trace_path else None

    @staticmethod
    def around(
        count: int,
        center_lat: float,
        center_lon: float,
        spacing_deg: float = 0.012,
        device_prefix: str = "QM-SIM",
    ) -> list[VirtualPhone]:
        side = math.ceil(math.sqrt(count))
        phones: list[VirtualPhone] = []
        for index in range(count):
            row, column = divmod(index, side)
            latitude = center_lat + (row - (side - 1) / 2) * spacing_deg
            longitude = center_lon + (column - (side - 1) / 2) * spacing_deg
            phones.append(
                VirtualPhone(f"{device_prefix}-{index + 1:04d}", latitude, longitude)
            )
        return phones

    def _record(
        self,
        kind: str,
        device: VirtualPhone,
        payload: dict,
        result: dict | None,
        error: str | None,
        truth: dict | None = None,
    ) -> None:
        row = {
            "trace_time_ms": int(time.time() * 1000),
            "kind": kind,
            "device_id": device.device_id,
            "payload": payload,
            "result": result,
            "error": error,
        }
        if truth is not None:
            row["simulator_truth"] = truth
        self.trace.append(row)

    def _send_heartbeat(self, phone: VirtualPhone, timestamp_ms: int) -> None:
        payload = {
            "schema_version": "1.0",
            "device_id": phone.device_id,
            "seq": phone.next_seq(),
            "observed_at_ms": timestamp_ms,
            "latitude": phone.latitude,
            "longitude": phone.longitude,
        }
        try:
            result = self.transport.heartbeat(phone.device_id, payload)
            self._record("heartbeat", phone, payload, result, None)
        except Exception as exc:
            self._record("heartbeat", phone, payload, None, repr(exc))

    def heartbeat_all(self, timestamp_ms: int | None = None, workers: int = 16) -> None:
        timestamp_ms = timestamp_ms or int(time.time() * 1000)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda phone: self._send_heartbeat(phone, timestamp_ms), self.phones))
        self.flush_trace()

    def trigger_devices(
        self,
        indices: list[int],
        base_timestamp_ms: int | None = None,
        packet_loss_fraction: float = 0.0,
        network_jitter_ms: int = 0,
        propagation_interval_ms: int = 70,
        truth_label: str = "synthetic_distributed_motion",
        *,
        base_ts: int | None = None,
        jitter_ms: int | None = None,
    ) -> None:
        # V1 Python-call aliases remain supported; the V2 catalog uses unitful names.
        if base_ts is not None:
            base_timestamp_ms = base_ts
        if jitter_ms is not None:
            network_jitter_ms = jitter_ms
        max_propagation = max(0, len(indices) - 1) * propagation_interval_ms
        if base_timestamp_ms is None:
            base_timestamp_ms = int(time.time() * 1000) - max_propagation
        jobs: list[tuple[VirtualPhone, dict, dict, int]] = []
        for ordinal, index in enumerate(indices):
            phone = self.phones[index]
            propagation_ms = ordinal * propagation_interval_ms
            network_delay_ms = self.rng.randint(0, network_jitter_ms) if network_jitter_ms else 0
            truth = {
                "scenario": truth_label,
                "injected": True,
                "ordinal": ordinal,
                "propagation_ms": propagation_ms,
                "network_delay_ms": network_delay_ms,
            }
            if self.rng.random() < packet_loss_fraction:
                self._record("trigger_dropped_by_simulator", phone, {}, None, None, truth)
                continue
            observed_at_ms = base_timestamp_ms + propagation_ms
            payload = {
                "schema_version": "1.0",
                "device_id": phone.device_id,
                "seq": phone.next_seq(),
                "observed_at_ms": observed_at_ms,
                "latitude": phone.latitude,
                "longitude": phone.longitude,
                "motion_rms": round(self.rng.uniform(1.0, 1.8), 4),
                "motion_peak": round(self.rng.uniform(2.0, 3.2), 4),
            }
            jobs.append((phone, payload, truth, network_delay_ms))

        def send(job: tuple[VirtualPhone, dict, dict, int]) -> None:
            phone, payload, truth, network_delay_ms = job
            if network_delay_ms:
                time.sleep(network_delay_ms / 1000.0)
            try:
                result = self.transport.trigger(phone.device_id, payload)
                self._record("trigger", phone, payload, result, None, truth)
            except Exception as exc:
                self._record("trigger", phone, payload, None, repr(exc), truth)

        with ThreadPoolExecutor(max_workers=min(32, max(1, len(jobs)))) as executor:
            list(executor.map(send, jobs))
        self.flush_trace()

    def inject_scenario(self, name: str, parameters: dict[str, int | float] | None = None) -> None:
        effective = parameters or {}
        propagation_ms = int(effective.get("trigger_propagation_interval_ms", 70))
        if name == "isolated":
            self.trigger_devices([0], truth_label="isolated_false_positive")
            return
        if name == "same-cell":
            count = min(6, len(self.phones))
            anchor = (self.phones[0].latitude, self.phones[0].longitude)
            original = [(phone.latitude, phone.longitude) for phone in self.phones[:count]]
            try:
                for phone in self.phones[:count]:
                    phone.latitude, phone.longitude = anchor
                self.trigger_devices(
                    list(range(count)),
                    propagation_interval_ms=propagation_ms,
                    truth_label="same_cell_negative",
                )
            finally:
                for phone, position in zip(self.phones[:count], original):
                    phone.latitude, phone.longitude = position
            return
        if name == "distributed":
            self.trigger_devices(
                list(range(min(8, len(self.phones)))),
                propagation_interval_ms=propagation_ms,
                truth_label="distributed_positive",
            )
            return
        if name == "degraded":
            self.trigger_devices(
                list(range(min(16, len(self.phones)))),
                packet_loss_fraction=float(effective.get("packet_loss_fraction", 0.25)),
                network_jitter_ms=int(effective.get("network_jitter_ms", 900)),
                propagation_interval_ms=propagation_ms,
                truth_label="distributed_degraded_network",
            )
            return
        raise ValueError(f"unknown scenario: {name}")

    def scenario(self, name: str, parameters: dict[str, int | float] | None = None) -> None:
        self.heartbeat_all()
        self.inject_scenario(name, parameters)

    def collect_transport_alerts(self) -> int:
        drain = getattr(self.transport, "drain_alerts", None)
        if not callable(drain):
            return 0
        alerts = drain()
        for alert in alerts:
            self.trace.append(
                {
                    "trace_time_ms": int(alert.get("received_at_ms", time.time() * 1000)),
                    "kind": "alert_received",
                    "device_id": str(alert.get("device_id", "unknown")),
                    "payload": alert.get("payload", {}),
                    "result": {
                        "topic": alert.get("topic"),
                        "dup": bool(alert.get("dup", False)),
                    },
                    "error": None,
                }
            )
        self.flush_trace()
        return len(alerts)

    def flush_trace(self) -> None:
        if self.trace_path:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            self.trace_path.write_text(
                json.dumps({"trace_schema": "1.0", "records": self.trace}, indent=2),
                encoding="utf-8",
            )
