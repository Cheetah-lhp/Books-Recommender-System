from __future__ import annotations

from pathlib import Path
from typing import Any


def train_popularity(spark, config: dict[str, Any], run_dir: Path) -> None:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    processed = Path(config["paths"]["processed"])
    train = spark.read.parquet(str(processed / "interactions")).filter(F.col("split") == "train")
    books = spark.read.parquet(str(processed / "books"))
    destination = run_dir / "models" / "popularity"

    all_scores = (
        train.groupBy("item_idx", "work_id")
        .agg(
            F.count(F.lit(1)).alias("positive_count"),
            F.sum("strength").alias("strength_sum"),
            F.avg("strength").alias("strength_mean"),
        )
        .withColumn("score", F.log1p("positive_count") * F.col("strength_mean"))
    )
    top_n = int(config["models"]["popularity"]["top_n"])
    global_scores = all_scores.orderBy(F.desc("score"), F.asc("item_idx")).limit(top_n)
    global_scores.write.mode("overwrite").parquet(str(destination / "global"))

    genre_scores = (
        books.select("item_idx", F.explode_outer("genres").alias("genre"))
        .join(all_scores.select("item_idx", "score", "positive_count"), "item_idx", "inner")
        .withColumn(
            "rank",
            F.row_number().over(
                Window.partitionBy("genre").orderBy(F.desc("score"), F.asc("item_idx"))
            ),
        )
        .filter(F.col("rank") <= top_n)
    )
    genre_scores.write.mode("overwrite").partitionBy("genre").parquet(str(destination / "by_genre"))


def popularity_candidates(spark, run_dir: Path, users, limit: int):
    from pyspark.sql import functions as F

    scores = (
        spark.read.parquet(str(run_dir / "models" / "popularity" / "global"))
        .orderBy(F.desc("score"), F.asc("item_idx"))
        .limit(int(limit))
        .select("item_idx", F.col("score").cast("double").alias("score"))
    )
    return users.select("user_id").distinct().crossJoin(F.broadcast(scores))
