from __future__ import annotations

from math import isfinite
from typing import Any

from .models import DeviceHeartbeat, TelemetryTrigger


class ValidationError(ValueError):
    pass


def _need(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValidationError(f"missing required field: {key}")
    return data[key]


def _reject_unknown(data: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ValidationError(f"unsupported field(s): {', '.join(unknown)}")


def _device_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValidationError("device_id must be a string")
    if len(value) < 4 or len(value) > 96:
        raise ValidationError("device_id must be 4..96 characters")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_:.@")
    if any(ch not in allowed for ch in value):
        raise ValidationError("device_id contains unsupported characters")
    return value


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ValidationError(f"{name} must be finite")
    return result


def _lat(value: Any) -> float:
    v = _number(value, "latitude")
    if not -90 <= v <= 90:
        raise ValidationError("latitude outside [-90,90]")
    return v


def _lon(value: Any) -> float:
    v = _number(value, "longitude")
    if not -180 <= v <= 180:
        raise ValidationError("longitude outside [-180,180]")
    return v


def _seq(value: Any) -> int:
    v = _integer(value, "seq")
    if v < 0:
        raise ValidationError("seq must be non-negative")
    return v


def _observed_at(value: Any) -> int:
    v = _integer(value, "observed_at_ms")
    if v < 0:
        raise ValidationError("observed_at_ms must be non-negative")
    return v


def parse_trigger(data: dict[str, Any], transport: str = "unknown") -> TelemetryTrigger:
    allowed = {
        "schema_version", "device_id", "seq", "observed_at_ms",
        "latitude", "longitude", "motion_rms", "motion_peak",
    }
    _reject_unknown(data, allowed)
    if _need(data, "schema_version") != "1.0":
        raise ValidationError("unsupported schema_version")
    rms = _number(_need(data, "motion_rms"), "motion_rms")
    peak = _number(_need(data, "motion_peak"), "motion_peak")
    if rms < 0 or peak < 0:
        raise ValidationError("motion values must be non-negative")
    return TelemetryTrigger(
        schema_version="1.0",
        device_id=_device_id(_need(data, "device_id")),
        seq=_seq(_need(data, "seq")),
        observed_at_ms=_observed_at(_need(data, "observed_at_ms")),
        latitude=_lat(_need(data, "latitude")),
        longitude=_lon(_need(data, "longitude")),
        motion_rms=rms,
        motion_peak=peak,
        transport=transport,
    )


def parse_heartbeat(data: dict[str, Any], transport: str = "unknown") -> DeviceHeartbeat:
    allowed = {
        "schema_version", "device_id", "seq", "observed_at_ms",
        "latitude", "longitude", "fcm_token",
    }
    _reject_unknown(data, allowed)
    if _need(data, "schema_version") != "1.0":
        raise ValidationError("unsupported schema_version")
    token = data.get("fcm_token")
    if token is not None and not isinstance(token, str):
        raise ValidationError("fcm_token must be a string")
    if token is not None and len(token) > 4096:
        raise ValidationError("fcm_token too long")
    return DeviceHeartbeat(
        schema_version="1.0",
        device_id=_device_id(_need(data, "device_id")),
        seq=_seq(_need(data, "seq")),
        observed_at_ms=_observed_at(_need(data, "observed_at_ms")),
        latitude=_lat(_need(data, "latitude")),
        longitude=_lon(_need(data, "longitude")),
        transport=transport,
        fcm_token=token or None,
    )


def validate_observation_time(observed_at_ms: int, received_at_ms: int, max_clock_skew_ms: int) -> None:
    """Reject observations whose device clock is implausibly far from cloud receipt time."""
    if observed_at_ms < 0:
        raise ValidationError("observed_at_ms must be non-negative")
    if abs(received_at_ms - observed_at_ms) > max_clock_skew_ms:
        raise ValidationError("observed_at_ms outside allowed clock-skew window")
