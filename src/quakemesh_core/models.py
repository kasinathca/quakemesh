from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class EventStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class TelemetryTrigger:
    schema_version: str
    device_id: str
    seq: int
    observed_at_ms: int
    latitude: float
    longitude: float
    motion_rms: float
    motion_peak: float
    transport: str = "unknown"


@dataclass(frozen=True)
class DeviceHeartbeat:
    schema_version: str
    device_id: str
    seq: int
    observed_at_ms: int
    latitude: float
    longitude: float
    transport: str = "unknown"
    fcm_token: str | None = None


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    device_id: str
    seq: int
    observed_at_ms: int
    h3_cell: str
    correlation_cell: str
    motion_rms: float
    motion_peak: float
    transport: str


@dataclass
class EventRecord:
    event_id: str
    status: EventStatus
    created_at_ms: int
    updated_at_ms: int
    first_observed_at_ms: int
    last_observed_at_ms: int
    device_ids: list[str] = field(default_factory=list)
    detection_footprint: list[str] = field(default_factory=list)
    warning_frontier: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    version: int = 1

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


@dataclass(frozen=True)
class DetectionDecision:
    confirmed: bool
    device_ids: tuple[str, ...]
    cells: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    first_observed_at_ms: int | None
    last_observed_at_ms: int | None
    reason: str
