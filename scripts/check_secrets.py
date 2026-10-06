from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE_PARTS = {
    ".git",
    ".venv",
    ".venv-cdk",
    "__pycache__",
    "artifacts",
    "cdk.out",
    ".pytest_cache",
    "node_modules",
    "dist",
    "playwright-report",
    "test-results",
}
PATTERNS = [
    ("AWS access key", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("private key", re.compile("-----BEGIN " + "(?:RSA |EC )?PRIVATE KEY-----")),
    ("Google private key", re.compile(r'"private_key"\s*:\s*"-----BEGIN')),
]
SENSITIVE_GENERATED = [
    Path("android/app/google-services.json"),
    Path("android/local.properties"),
    Path("artifacts/runtime-config.json"),
]


def tracked(path: Path) -> bool:
    if not (ROOT / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path.as_posix()],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


findings: list[tuple[str, Path]] = []
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in path.parts for part in IGNORE_PARTS) or path.name == Path(__file__).name:
        continue
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".jar", ".zip", ".pdf", ".ico"}:
        continue
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    for name, regex in PATTERNS:
        if regex.search(text):
            findings.append((name, path.relative_to(ROOT)))

for rel in SENSITIVE_GENERATED:
    if (ROOT / rel).exists() and tracked(rel):
        findings.append(("generated credential/config file is TRACKED", rel))

if findings:
    for kind, path in findings:
        print(f"SECRET-SCAN: {kind}: {path}")
    sys.exit(1)
print("Secret scan: clean (generated ignored credentials may exist locally, but none are scanned as tracked source)")
