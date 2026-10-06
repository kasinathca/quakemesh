from __future__ import annotations

import argparse
import json
import py_compile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md",
    "NEXT_STEPS.md",
    "NEW_REPO_SETUP_AND_PUSH.md",
    "requirements.txt",
    "src/quakemesh_core/correlation.py",
    "local_runtime/app.py",
    "local_runtime/scenarios.py",
    "simulator/cli.py",
    "aws/infrastructure/stack.py",
    "aws/lambdas/ingress.py",
    "dashboard/index.html",
    "dashboard/package.json",
    "dashboard/package-lock.json",
    "dashboard/src/app/App.tsx",
    "dashboard/src/features/scenarios/ScenarioLab.tsx",
    "android/app/src/main/AndroidManifest.xml",
    "docs/v2/QM-V2-TRACEABILITY.md",
)
IGNORED_PARTS = {
    ".venv",
    ".venv-cdk",
    "node_modules",
    "artifacts",
    "cdk.out",
    "playwright-report",
    "test-results",
}


def compile_python() -> None:
    failures: list[tuple[Path, Exception]] = []
    for path in ROOT.rglob("*.py"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as error:
            failures.append((path, error))
    if failures:
        detail = "; ".join(f"{path}: {error}" for path, error in failures)
        raise RuntimeError(f"Python compilation failed: {detail}")
    print("Python compilation: clean")


def audit_repository() -> None:
    missing = [relative for relative in REQUIRED if not (ROOT / relative).exists()]
    if missing:
        raise RuntimeError(f"Missing required files: {', '.join(missing)}")
    json_files = [
        *(ROOT / "schemas").glob("*.json"),
        ROOT / "experiments" / "scenarios.json",
        ROOT / "dashboard" / "package.json",
        ROOT / "dashboard" / "package-lock.json",
    ]
    for path in json_files:
        json.loads(path.read_text(encoding="utf-8"))
    for path in (ROOT / "android" / "app" / "src" / "main").rglob("*.xml"):
        ET.parse(path)
    print("Repository structural audit: clean")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-only", action="store_true")
    arguments = parser.parse_args()
    compile_python()
    if not arguments.compile_only:
        audit_repository()


if __name__ == "__main__":
    main()
