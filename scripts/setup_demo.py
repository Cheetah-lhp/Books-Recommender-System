"""Install the portable demo bundle; no Spark or machine-specific paths needed."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

RUN_ID = "remote-demo"
ARCHIVE_NAME = "remote-demo-serving.tar.gz"


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def package_bundle(root: Path) -> dict:
    """Maintainer command: snapshot only serving tables, excluding training files."""
    source = root / "artifacts" / RUN_ID / "serving"
    model = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    destination = root / "demo_assets"
    destination.mkdir(exist_ok=True)
    files = [source / "manifest.json"]
    for table in ("items", "aliases", "als_items"):
        parts = sorted((source / table).glob("*.parquet"))
        if not parts:
            raise FileNotFoundError(f"Missing serving table: {table}")
        files.extend(parts)
    archive_path = destination / ARCHIVE_NAME
    if archive_path.exists():
        raise FileExistsError(f"Bundle already exists: {archive_path}")
    hashes = {}
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in files:
            relative = "serving/" + path.relative_to(source).as_posix()
            archive.add(path, arcname=relative, recursive=False)
            hashes[relative] = sha256(path)
    manifest = {
        "version": 1,
        "run_id": RUN_ID,
        "archive": ARCHIVE_NAME,
        "sha256": sha256(archive_path),
        "bytes": archive_path.stat().st_size,
        "items": model["items"],
        "book_id_namespace": model["book_id_namespace"],
        "files": hashes,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def prepare_bundle(root: Path) -> Path:
    assets = root / "demo_assets"
    manifest = json.loads((assets / "manifest.json").read_text(encoding="utf-8"))
    if manifest["run_id"] != RUN_ID or manifest["archive"] != ARCHIVE_NAME:
        raise ValueError("Unexpected bundled run")
    archive_path = assets / ARCHIVE_NAME
    if sha256(archive_path) != manifest["sha256"]:
        raise ValueError("Demo archive checksum mismatch; restore demo_assets from Git.")
    artifacts = root / "artifacts"
    target = artifacts / RUN_ID
    if target.exists():
        model_file = target / "serving" / "manifest.json"
        if model_file.exists():
            model = json.loads(model_file.read_text(encoding="utf-8"))
            if model.get("run_id") == RUN_ID:
                return target
        raise FileExistsError(f"An incomplete run exists at {target}; move it before setup.")
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".demo-setup-", dir=artifacts) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            if {member.name for member in members} != set(manifest["files"]):
                raise ValueError("Unexpected files in demo archive")
            for member in members:
                relative = PurePosixPath(member.name)
                if (
                    not member.isfile()
                    or relative.is_absolute()
                    or ".." in relative.parts
                    or not relative.parts
                    or relative.parts[0] != "serving"
                ):
                    raise ValueError("Invalid demo archive member")
                data = archive.extractfile(member)
                if data is None:
                    raise ValueError("Missing demo archive content")
                output = stage.joinpath(*relative.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                with data, output.open("wb") as handle:
                    shutil.copyfileobj(data, handle)
                if sha256(output) != manifest["files"][member.name]:
                    raise ValueError(f"Demo file checksum mismatch: {member.name}")
        (stage / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": RUN_ID,
                    "status": "serving-ready",
                    "serving": "serving/manifest.json",
                    "source": f"demo_assets/{ARCHIVE_NAME}",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        # A serving bundle needs no processed-data paths or training configuration.
        shutil.move(str(stage), str(target))
    latest = artifacts / "LATEST"
    if not latest.exists():
        latest.write_text(RUN_ID, encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="Install runtime dependencies")
    parser.add_argument("--package", action="store_true", help="Maintainer: build demo asset")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    if args.package:
        print(json.dumps(package_bundle(root), indent=2))
        return
    if args.install:
        if not (3, 11) <= sys.version_info[:2] <= (3, 13):
            raise SystemExit(
                "Demo setup requires Python 3.11-3.13. Create .venv with py -3.11 -m venv .venv."
            )
        runtime_env = {**os.environ, "PYTHONUTF8": "1"}
        # A normal wheel avoids locale-encoded editable .pth paths on Python 3.11/Windows.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", ".[serve]"],
            cwd=root,
            env=runtime_env,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pymysql>=1.1,<2", "python-dotenv>=1,<2"],
            env=runtime_env,
            check=True,
        )
    target = prepare_bundle(root)
    # Escape non-ASCII paths for older Windows console encodings.
    print(json.dumps({"run_id": RUN_ID, "ready": True, "path": str(target)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
