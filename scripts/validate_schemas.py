from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "schemas"
REQUIRED_V2 = {
    "v2-error-envelope.schema.json",
    "v2-scenario-run.schema.json",
    "v2-stage.schema.json",
    "v2-telemetry-event.schema.json",
}


def main() -> None:
    schemas: dict[str, dict] = {}
    for path in sorted(SCHEMA_ROOT.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise RuntimeError(f"{path.name}: unsupported or missing JSON Schema dialect")
        if schema.get("type") != "object" or not isinstance(schema.get("properties"), dict):
            raise RuntimeError(f"{path.name}: root must define object properties")
        schemas[path.name] = schema
    missing = REQUIRED_V2 - schemas.keys()
    if missing:
        raise RuntimeError(f"Missing V2 schemas: {sorted(missing)}")
    serialized_v2 = json.dumps(
        {name: schemas[name] for name in REQUIRED_V2},
        sort_keys=True,
    ).lower()
    for forbidden in ("fcm_token", "latitude", "longitude", "credential", "private_key"):
        if forbidden in serialized_v2:
            raise RuntimeError(f"V2 control/observability schemas expose forbidden field: {forbidden}")
    for name in REQUIRED_V2:
        for reference in _references(schemas[name]):
            if reference.startswith("http") or reference.startswith("#"):
                continue
            if reference not in schemas:
                raise RuntimeError(f"{name}: unresolved schema reference {reference}")
    print(f"Schema validation: {len(schemas)} schemas parsed; V2 references and privacy fields clean")


def _references(value: object) -> list[str]:
    if isinstance(value, dict):
        found = [value["$ref"]] if isinstance(value.get("$ref"), str) else []
        for child in value.values():
            found.extend(_references(child))
        return found
    if isinstance(value, list):
        found = []
        for child in value:
            found.extend(_references(child))
        return found
    return []


if __name__ == "__main__":
    main()
