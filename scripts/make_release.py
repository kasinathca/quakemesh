from __future__ import annotations

import argparse
import hashlib
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv-cdk",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "cdk.out",
    ".idea",
    ".vscode",
}
EXCLUDED_RELATIVE = {
    Path("android/local.properties"),
    Path("android/app/google-services.json"),
    Path("dashboard/config.aws.js"),
    Path("artifacts/runtime-config.json"),
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt"}
GENERATED_SUFFIXES = {".pyc", ".pyo"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel in EXCLUDED_RELATIVE:
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return False
    if rel.parts and rel.parts[0] == "artifacts" and rel != Path("artifacts/.gitkeep"):
        return False
    if path.suffix.lower() in SECRET_SUFFIXES | GENERATED_SUFFIXES | {".zip", ".sha256"}:
        return False
    return path.is_file()


def clean_generated() -> None:
    for directory in list(ROOT.rglob("__pycache__")) + list(ROOT.rglob(".pytest_cache")) + list(ROOT.rglob(".ruff_cache")):
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)
    for directory in [ROOT / "aws/infrastructure/cdk.out", ROOT / "cdk.out"]:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
    artifacts = ROOT / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for child in artifacts.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def source_files(include_manifest: bool = False) -> list[Path]:
    files = [p for p in ROOT.rglob("*") if should_include(p)]
    manifest = ROOT / "SOURCE_MANIFEST.txt"
    if not include_manifest:
        files = [p for p in files if p != manifest]
    return sorted(files, key=lambda p: p.relative_to(ROOT).as_posix())


def write_manifest() -> Path:
    manifest = ROOT / "SOURCE_MANIFEST.txt"
    lines = [
        "# QuakeMesh source manifest",
        "# SHA-256  relative/path",
        "# The manifest intentionally excludes itself, generated artifacts, caches, credentials, and release ZIPs.",
    ]
    for path in source_files(include_manifest=False):
        lines.append(f"{sha256_file(path)}  {path.relative_to(ROOT).as_posix()}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def build_zip(output: Path) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    checksum_file = output.with_suffix(output.suffix + ".sha256")
    checksum_file.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in source_files(include_manifest=True):
            arcname = Path("QuakeMesh") / path.relative_to(ROOT)
            archive.write(path, arcname.as_posix())
    digest = sha256_file(output)
    checksum_file.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return output, checksum_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean QuakeMesh source release ZIP")
    parser.add_argument("--output", default=str(ROOT.parent / "QuakeMesh-v1.0.1.zip"))
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    if not args.no_clean:
        clean_generated()
    manifest = write_manifest()
    output, checksum = build_zip(Path(args.output).resolve())
    print(f"manifest {manifest}")
    print(f"zip {output}")
    print(f"checksum {checksum}")
    print(f"files {len(source_files(include_manifest=True))}")


if __name__ == "__main__":
    main()
