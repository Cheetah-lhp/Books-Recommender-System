from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from books_recommender.artifacts import create_run, update_manifest
from books_recommender.models.als import train_als
from books_recommender.models.content import train_content
from books_recommender.models.item_item import train_item_item
from books_recommender.models.popularity import train_popularity

AVAILABLE_MODELS = ("popularity", "item_item", "als", "content", "hybrid")


def normalize_models(models: Iterable[str]) -> list[str]:
    values = [value.strip().lower().replace("-", "_") for value in models if value.strip()]
    if not values or "all" in values:
        return list(AVAILABLE_MODELS)
    unknown = sorted(set(values) - set(AVAILABLE_MODELS))
    if unknown:
        raise ValueError(f"Unknown models: {', '.join(unknown)}")
    if "hybrid" in values:
        values = list(dict.fromkeys(["popularity", "als", "content", *values]))
    return values


def train_models(
    spark,
    config: dict[str, Any],
    models: Iterable[str],
    run_id: str | None = None,
) -> tuple[str, Path]:
    processed = Path(config["paths"]["processed"])
    if not (processed / "manifest.json").exists():
        raise FileNotFoundError(
            f"Prepared data not found in {processed}. Run the 'prepare' command first."
        )
    selected = normalize_models(models)
    identifier, run_dir = create_run(config, run_id)
    update_manifest(run_dir, status="training", models=selected)
    trainers = {
        "popularity": train_popularity,
        "item_item": train_item_item,
        "als": train_als,
        "content": train_content,
    }
    for name in selected:
        if name in trainers:
            trainers[name](spark, config, run_dir)
    if config.get("serving", {}).get("enabled") and {"als", "content"}.issubset(selected):
        from books_recommender.serving.export import export_serving

        export_serving(spark, config, run_dir)
    update_manifest(run_dir, status="trained")
    return identifier, run_dir
