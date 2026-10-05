from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path
from typing import Protocol


class Transport(Protocol):
    def heartbeat(self, device_id: str, payload: dict) -> dict: ...
    def trigger(self, device_id: str, payload: dict) -> dict: ...
    def close(self) -> None: ...


class HttpTransport:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: float = 10, run_id: str | None = None):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.run_id = run_id

    def _post(self, path: str, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        if self.run_id:
            headers["x-quakemesh-run-id"] = self.run_id
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def heartbeat(self, device_id: str, payload: dict) -> dict:
        return self._post("/v1/devices/heartbeat", payload)

    def trigger(self, device_id: str, payload: dict) -> dict:
        return self._post("/v1/evidence/trigger", payload)

    def close(self) -> None:
        pass


class AwsIotTransport:
    """One long-lived MQTT/mTLS connection per virtual phone/Thing.

    Every connection also subscribes to its Thing-scoped alert topic. Received
    warnings are retained in-memory so the experiment trace can prove cloud-to-edge
    delivery without a separate MQTT test client.
    """

    def __init__(self, endpoint: str, cert_dir: str | Path, root_ca: str | Path):
        try:
            from awscrt import mqtt
            from awsiot import mqtt_connection_builder
        except ImportError as exc:
            raise RuntimeError("Install awsiotsdk to use --transport mqtt") from exc
        self.mqtt = mqtt
        self.builder = mqtt_connection_builder
        self.endpoint = endpoint
        self.cert_dir = Path(cert_dir)
        self.root_ca = str(root_ca)
        self.connections: dict[str, object] = {}
        self._alerts: list[dict] = []
        self._seen_alerts: set[tuple[str, str]] = set()
        self._lock = threading.RLock()

    def _on_alert(self, device_id: str):
        def callback(topic, payload, dup, qos, retain, **kwargs):
            try:
                decoded = json.loads(bytes(payload).decode("utf-8"))
            except Exception:
                decoded = {"raw": bytes(payload).decode("utf-8", errors="replace")}
            event_id = str(decoded.get("event_id", ""))
            key = (device_id, event_id)
            with self._lock:
                if event_id and key in self._seen_alerts:
                    return
                if event_id:
                    self._seen_alerts.add(key)
                self._alerts.append(
                    {
                        "received_at_ms": int(time.time() * 1000),
                        "device_id": device_id,
                        "topic": str(topic),
                        "payload": decoded,
                        "dup": bool(dup),
                    }
                )
        return callback

    def _conn(self, device_id: str):
        if device_id in self.connections:
            return self.connections[device_id]
        cert = self.cert_dir / device_id / "certificate.pem.crt"
        key = self.cert_dir / device_id / "private.pem.key"
        if not cert.exists() or not key.exists():
            raise FileNotFoundError(f"Missing certificate files for {device_id} under {self.cert_dir}")
        connection = self.builder.mtls_from_path(
            endpoint=self.endpoint,
            cert_filepath=str(cert),
            pri_key_filepath=str(key),
            ca_filepath=self.root_ca,
            client_id=device_id,
            clean_session=False,
            keep_alive_secs=30,
        )
        connection.connect().result(timeout=15)
        connection.subscribe(
            topic=f"quakemesh/v1/devices/{device_id}/alerts",
            qos=self.mqtt.QoS.AT_LEAST_ONCE,
            callback=self._on_alert(device_id),
        ).result(timeout=10)
        self.connections[device_id] = connection
        return connection

    def _publish(self, device_id: str, kind: str, payload: dict) -> dict:
        topic = f"quakemesh/v1/devices/{device_id}/{kind}"
        self._conn(device_id).publish(
            topic=topic,
            payload=json.dumps(payload),
            qos=self.mqtt.QoS.AT_LEAST_ONCE,
        ).result(timeout=10)
        return {"published": True, "topic": topic}

    def heartbeat(self, device_id: str, payload: dict) -> dict:
        return self._publish(device_id, "heartbeat", payload)

    def trigger(self, device_id: str, payload: dict) -> dict:
        return self._publish(device_id, "trigger", payload)

    def drain_alerts(self) -> list[dict]:
        with self._lock:
            out = list(self._alerts)
            self._alerts.clear()
        return out

    def close(self) -> None:
        for connection in self.connections.values():
            try:
                connection.disconnect().result(timeout=5)
            except Exception:
                pass
        self.connections.clear()
