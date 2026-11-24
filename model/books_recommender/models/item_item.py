from __future__ import annotations

from pathlib import Path
from typing import Any


def train_item_item(spark, config: dict[str, Any], run_dir: Path) -> None:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    options = config["models"]["item_item"]
    train = spark.read.parquet(str(Path(config["paths"]["processed"]) / "interactions")).filter(
        F.col("split") == "train"
    )
    history_window = Window.partitionBy("user_id").orderBy(F.desc("strength"), F.asc("item_idx"))
    capped = (
        train.withColumn("history_rank", F.row_number().over(history_window))
        .filter(F.col("history_rank") <= int(options["max_history"]))
        .select("user_id", "item_idx")
        .dropDuplicates()
    )
    item_counts = capped.groupBy("item_idx").agg(F.countDistinct("user_id").alias("user_count"))
    left = capped.alias("left")
    right = capped.alias("right")
    pairs = (
        left.join(
            right,
            (F.col("left.user_id") == F.col("right.user_id"))
            & (F.col("left.item_idx") < F.col("right.item_idx")),
            "inner",
        )
        .groupBy(
            F.col("left.item_idx").alias("item_a"),
            F.col("right.item_idx").alias("item_b"),
        )
        .agg(F.count(F.lit(1)).alias("cooccurrence"))
        .filter(F.col("cooccurrence") >= int(options["min_cooccurrence"]))
    )
    count_a = item_counts.select(
        F.col("item_idx").alias("item_a"), F.col("user_count").alias("count_a")
    )
    count_b = item_counts.select(
        F.col("item_idx").alias("item_b"), F.col("user_count").alias("count_b")
    )
    scored = (
        pairs.join(count_a, "item_a")
        .join(count_b, "item_b")
        .withColumn(
            "similarity", F.col("cooccurrence") / F.sqrt(F.col("count_a") * F.col("count_b"))
        )
    )
    symmetric = scored.select(
        F.col("item_a").alias("item_idx"),
        F.col("item_b").alias("neighbor_idx"),
        "similarity",
        "cooccurrence",
    ).unionByName(
        scored.select(
            F.col("item_b").alias("item_idx"),
            F.col("item_a").alias("neighbor_idx"),
            "similarity",
            "cooccurrence",
        )
    )
    neighbor_window = Window.partitionBy("item_idx").orderBy(
        F.desc("similarity"), F.desc("cooccurrence"), F.asc("neighbor_idx")
    )
    neighbors = symmetric.withColumn("rank", F.row_number().over(neighbor_window)).filter(
        F.col("rank") <= int(options["top_n"])
    )
    neighbors.write.mode("overwrite").parquet(str(run_dir / "models" / "item_item" / "neighbors"))


def item_item_candidates(spark, run_dir: Path, history, limit: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    neighbors = spark.read.parquet(str(run_dir / "models" / "item_item" / "neighbors"))
    scored = (
        history.select("user_id", "item_idx", "strength")
        .join(neighbors, "item_idx", "inner")
        .groupBy("user_id", F.col("neighbor_idx").alias("item_idx"))
        .agg(F.sum(F.col("similarity") * F.col("strength")).alias("score"))
    )
    window = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return scored.withColumn("rank", F.row_number().over(window)).filter(
        F.col("rank") <= int(limit)
    )
