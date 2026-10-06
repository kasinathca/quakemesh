from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CATALOG_VERSION = "2.0"


@dataclass(frozen=True)
class ParameterSpec:
    name: str
    value_type: str
    default: int | float
    minimum: int | float
    maximum: int | float
    unit: str
    description: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.value_type,
            "default": self.default,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    title: str
    purpose: str
    expected_result: str
    parameter_names: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.scenario_id,
            "title": self.title,
            "purpose": self.purpose,
            "expected_result": self.expected_result,
            "catalog_version": CATALOG_VERSION,
            "supported_parameters": [PARAMETERS[name].as_dict() for name in self.parameter_names],
        }


PARAMETERS = {
    "devices": ParameterSpec(
        "devices",
        "integer",
        25,
        4,
        500,
        "devices",
        "Size of the virtual-phone fleet. Only the scenario-defined subset triggers.",
    ),
    "seed": ParameterSpec(
        "seed",
        "integer",
        42,
        0,
        2_147_483_647,
        "integer",
        "Deterministic pseudo-random seed.",
    ),
    "packet_loss_fraction": ParameterSpec(
        "packet_loss_fraction",
        "number",
        0.25,
        0.0,
        0.95,
        "fraction",
        "Fraction of generated trigger observations intentionally dropped by the simulator.",
    ),
    "network_jitter_ms": ParameterSpec(
        "network_jitter_ms",
        "integer",
        900,
        0,
        5_000,
        "milliseconds",
        "Maximum deterministic network delivery delay.",
    ),
    "trigger_propagation_interval_ms": ParameterSpec(
        "trigger_propagation_interval_ms",
        "integer",
        70,
        0,
        1_000,
        "milliseconds",
        "Synthetic observation-time interval between successive triggered devices.",
    ),
}


SCENARIOS = {
    "isolated": ScenarioDefinition(
        "isolated",
        "Isolated disturbance",
        "Prove that one device cannot confirm an experimental event.",
        "NO_CONFIRMATION",
        ("devices", "seed"),
    ),
    "same-cell": ScenarioDefinition(
        "same-cell",
        "Same-cell cluster",
        "Prove that device count without coarse-H3 diversity is insufficient.",
        "NO_CONFIRMATION",
        ("devices", "seed", "trigger_propagation_interval_ms"),
    ),
    "distributed": ScenarioDefinition(
        "distributed",
        "Distributed corroboration",
        "Exercise the positive geographically diverse corroboration path.",
        "CONFIRMATION",
        ("devices", "seed", "trigger_propagation_interval_ms"),
    ),
    "degraded": ScenarioDefinition(
        "degraded",
        "Degraded network",
        "Evaluate surviving evidence under deterministic packet loss and jitter.",
        "CONDITIONAL",
        (
            "devices",
            "seed",
            "packet_loss_fraction",
            "network_jitter_ms",
            "trigger_propagation_interval_ms",
        ),
    ),
}


def _coerce(spec: ParameterSpec, value: Any) -> int | float:
    if spec.value_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{spec.name} must be an integer")
        normalized: int | float = value
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{spec.name} must be a number")
        normalized = float(value)
    if normalized < spec.minimum or normalized > spec.maximum:
        raise ValueError(
            f"{spec.name} must be between {spec.minimum} and {spec.maximum} {spec.unit}"
        )
    return normalized


def normalize_parameters(
    scenario: str,
    *,
    devices: int | None = None,
    seed: int | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, int | float]:
    definition = SCENARIOS.get(scenario)
    if definition is None:
        raise ValueError("unknown scenario")
    supplied = dict(parameters or {})
    if devices is not None:
        if "devices" in supplied and supplied["devices"] != devices:
            raise ValueError("devices conflicts with parameters.devices")
        supplied["devices"] = devices
    if seed is not None:
        if "seed" in supplied and supplied["seed"] != seed:
            raise ValueError("seed conflicts with parameters.seed")
        supplied["seed"] = seed
    supported = set(definition.parameter_names)
    unknown = sorted(set(supplied) - supported)
    if unknown:
        raise ValueError(f"unsupported parameter(s) for {scenario}: {', '.join(unknown)}")
    return {
        name: _coerce(PARAMETERS[name], supplied.get(name, PARAMETERS[name].default))
        for name in definition.parameter_names
    }


def catalog_items() -> list[dict[str, Any]]:
    return [definition.as_dict() for definition in SCENARIOS.values()]
