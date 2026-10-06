from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str
    source: Literal["dashboard", "cli", "android", "test"] = "dashboard"
    devices: int | None = None
    seed: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class AlertAcknowledgementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acknowledgement_source: Literal["dashboard", "cli", "android", "test"]
    device_id: str | None = Field(default=None, min_length=1, max_length=128)


class V2Envelope(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    request_id: str
    data: Any


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    error: ErrorBody
