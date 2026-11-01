from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from books_recommender.config import dump_config, load_config


def create_run(config: dict[str, Any], run_id: str | None = None) -> tuple[str, Path]:
    identifier = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = Path(config["paths"]["artifacts"])
    run_dir = root / identifier
    if run_dir.exists():
        suffix = 1
        while (root / f"{identifier}-{suffix}").exists():
            suffix += 1
        identifier = f"{identifier}-{suffix}"
        run_dir = root / identifier
    run_dir.mkdir(parents=True)
    dump_config(config, run_dir / "config.yaml")
    (root / "LATEST").write_text(identifier, encoding="utf-8")
    write_json(
        run_dir / "manifest.json",
        {"run_id": identifier, "created_at": datetime.now(UTC).isoformat(), "status": "created"},
    )
    return identifier, run_dir


def resolve_run(artifacts_root: str | Path, run_id: str) -> Path:
    root = Path(artifacts_root)
    identifier = run_id
    if run_id.lower() == "latest":
        latest = root / "LATEST"
        if not latest.exists():
            raise FileNotFoundError(f"No LATEST run marker exists in {root}")
        identifier = latest.read_text(encoding="utf-8").strip()
    run_dir = root / identifier
    if not run_dir.exists():
        raise FileNotFoundError(f"Run does not exist: {run_dir}")
    return run_dir


def load_run(run_dir: Path) -> dict[str, Any]:
    return load_config(run_dir / "config.yaml")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, default=str)


def update_manifest(run_dir: Path, **updates: Any) -> None:
    path = run_dir / "manifest.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current.update(updates)
    write_json(path, current)
