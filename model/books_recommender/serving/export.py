from __future__ import annotations

import json
from pathlib import Path

from books_recommender.artifacts import update_manifest, write_json
from books_recommender.models.als import load_als


def export_serving(spark, config: dict, run_dir: Path) -> Path:
    """Write a bounded demo serving bundle with distributed Spark writers.

    Serving deliberately loads a small catalog into memory. Full-dataset training
    remains distributed; it must not silently create an unbounded serving bundle.
    """
    from pyspark.sql import functions as F

    processed = Path(config["paths"]["processed"])
    prepared = json.loads((processed / "manifest.json").read_text(encoding="utf-8"))
    if prepared.get("book_id_namespace") != "book_id_csv":
        raise ValueError("Prepared data has an old ID namespace. Run prepare and train again.")
    books = spark.read.parquet(str(processed / "books"))
    count = books.count()
    maximum = int(config.get("serving", {}).get("max_items", 50000))
    if count > maximum:
        raise ValueError(f"Serving catalog has {count} works; limit is {maximum}. Use demo.yaml.")
    features_path = run_dir / "models" / "content" / "features"
    als_path = run_dir / "models" / "als" / "model"
    if not features_path.exists() or not als_path.exists():
        raise ValueError("Serving requires ALS and content models. Train --models hybrid first.")
    destination = run_dir / "serving"
    train = spark.read.parquet(str(processed / "interactions")).filter("split = 'train'")
    popularity = train.groupBy("item_idx").agg(
        (F.log1p(F.count(F.lit(1))) * F.avg("strength")).alias("popularity")
    )
    features = spark.read.parquet(str(features_path)).select("item_idx", "features")
    items = (
        books.join(features, "item_idx")
        .join(popularity, "item_idx", "left")
        .fillna(0.0, subset=["popularity"])
        .select(
            "item_idx", "work_id", "canonical_book_id", "title", "genres", "features", "popularity"
        )
    )
    items.write.mode("overwrite").parquet(str(destination / "items"))
    spark.read.parquet(str(processed / "edition_to_work")).select(
        F.col("edition_id").cast("string").alias("source_book_id"), "item_idx"
    ).write.mode("overwrite").parquet(str(destination / "aliases"))
    load_als(run_dir).itemFactors.write.mode("overwrite").parquet(str(destination / "als_items"))
    parameters = json.loads((run_dir / "models" / "als" / "parameters.json").read_text())
    write_json(
        destination / "manifest.json",
        {
            "version": 1,
            "run_id": run_dir.name,
            "book_id_namespace": "book_id_csv",
            "items": count,
            "num_features": config["models"]["content"]["num_features"],
            "max_history": config["models"]["content"]["max_history"],
            "als": parameters,
            "hybrid": config["models"]["hybrid"],
        },
    )
    update_manifest(run_dir, serving="serving/manifest.json")
    return destination
