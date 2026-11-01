from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "sample",
    "seed": 42,
    "paths": {
        "raw": "data",
        "samples": "samples_data",
        "processed": "data/processed/sample",
        "artifacts": "artifacts",
        "checkpoints": "checkpoints/sample",
    },
    "spark": {
        "app_name": "BooksRecommender",
        "master": "local[*]",
        "driver_memory": "4g",
        "shuffle_partitions": 16,
    },
    "data": {
        "source": "raw_goodreads",
        "sample_users": 10000,
        "min_user_positives": 5,
        "split_strategy": "per_user",
        "generic_shelves": ["to-read", "read", "owned", "books-i-own", "currently-reading"],
        "max_shelves_per_book": 20,
    },
    "signals": {
        "base": 1.0,
        "read": 2.0,
        "reviewed": 2.0,
        "rating_bonus": {"3": 1.0, "4": 2.0, "5": 3.0},
        "excluded_ratings": [1, 2],
    },
}


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return current


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    config = _merge(DEFAULT_CONFIG, loaded)
    root = find_repo_root(config_path.parent)
    config["config_path"] = str(config_path)
    config["repo_root"] = str(root)
    for key in ("raw", "samples", "processed", "artifacts", "checkpoints"):
        value = Path(config["paths"][key])
        config["paths"][key] = str(value if value.is_absolute() else (root / value).resolve())
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if config["data"]["source"] not in {"raw_goodreads", "sample_parquet"}:
        raise ValueError("data.source must be 'raw_goodreads' or 'sample_parquet'")
    if config["mode"] not in {"sample", "full"}:
        raise ValueError("mode must be 'sample' or 'full'")
    if config["data"]["split_strategy"] not in {"per_user", "temporal_reviews"}:
        raise ValueError("split_strategy must be 'per_user' or 'temporal_reviews'")
    if int(config["data"]["min_user_positives"]) < 3:
        raise ValueError("min_user_positives must be at least 3")
    weights = config.get("models", {}).get("hybrid", {})
    if weights:
        total = sum(
            float(weights[name]) for name in ("als_weight", "content_weight", "popularity_weight")
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("hybrid warm-user weights must sum to 1")


def dump_config(config: dict[str, Any], path: Path) -> None:
    serializable = {
        key: value for key, value in config.items() if key not in {"config_path", "repo_root"}
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(serializable, handle, sort_keys=False, allow_unicode=True)
