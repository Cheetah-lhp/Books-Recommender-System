from __future__ import annotations

from typing import Any


def exclude_seen_and_rank(candidates, history, limit: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    seen = history.select("user_id", "item_idx").dropDuplicates()
    unseen = candidates.join(seen, ["user_id", "item_idx"], "left_anti")
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return (
        unseen.drop("rank")
        .withColumn("rank", F.row_number().over(ranking))
        .filter(F.col("rank") <= int(limit))
    )


def hybrid_candidates(als, content, popularity, config: dict[str, Any], limit: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    def tagged(frame, source: str):
        return frame.select(
            "user_id",
            "item_idx",
            F.lit(source).alias("source"),
            F.col("score").cast("double").alias("raw_score"),
        )

    long_scores = (
        tagged(als, "als")
        .unionByName(tagged(content, "content"))
        .unionByName(tagged(popularity, "popularity"))
    )
    component_window = Window.partitionBy("user_id", "source")
    normalized = (
        long_scores.withColumn("minimum", F.min("raw_score").over(component_window))
        .withColumn("maximum", F.max("raw_score").over(component_window))
        .withColumn(
            "normalized_score",
            F.when(F.col("maximum") == F.col("minimum"), F.lit(1.0)).otherwise(
                (F.col("raw_score") - F.col("minimum")) / (F.col("maximum") - F.col("minimum"))
            ),
        )
    )
    wide = (
        normalized.groupBy("user_id", "item_idx")
        .agg(
            F.max(F.when(F.col("source") == "als", F.col("normalized_score"))).alias("als_score"),
            F.max(F.when(F.col("source") == "content", F.col("normalized_score"))).alias(
                "content_score"
            ),
            F.max(F.when(F.col("source") == "popularity", F.col("normalized_score"))).alias(
                "popularity_score"
            ),
        )
        .fillna(0.0, subset=["als_score", "content_score", "popularity_score"])
    )
    options = config["models"]["hybrid"]
    scored = (
        wide.withColumn("als_contribution", F.col("als_score") * float(options["als_weight"]))
        .withColumn(
            "content_contribution", F.col("content_score") * float(options["content_weight"])
        )
        .withColumn(
            "popularity_contribution",
            F.col("popularity_score") * float(options["popularity_weight"]),
        )
        .withColumn(
            "score",
            F.col("als_contribution")
            + F.col("content_contribution")
            + F.col("popularity_contribution"),
        )
    )
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return scored.withColumn("rank", F.row_number().over(ranking)).filter(
        F.col("rank") <= int(limit)
    )


def cold_hybrid_candidates(content, popularity, config: dict[str, Any], limit: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    options = config["models"]["hybrid"]
    content = content.select("user_id", "item_idx", F.col("score").alias("content_raw"))
    popularity = popularity.select("user_id", "item_idx", F.col("score").alias("popularity_raw"))
    joined = content.join(popularity, ["user_id", "item_idx"], "full").fillna(
        0.0, subset=["content_raw", "popularity_raw"]
    )
    for column in ("content_raw", "popularity_raw"):
        window = Window.partitionBy("user_id")
        joined = (
            joined.withColumn(f"{column}_min", F.min(column).over(window))
            .withColumn(f"{column}_max", F.max(column).over(window))
            .withColumn(
                column.replace("_raw", "_score"),
                F.when(F.col(f"{column}_max") == F.col(f"{column}_min"), F.lit(1.0)).otherwise(
                    (F.col(column) - F.col(f"{column}_min"))
                    / (F.col(f"{column}_max") - F.col(f"{column}_min"))
                ),
            )
        )
    scored = (
        joined.withColumn("als_score", F.lit(0.0))
        .withColumn("als_contribution", F.lit(0.0))
        .withColumn(
            "content_contribution",
            F.col("content_score") * float(options["cold_content_weight"]),
        )
        .withColumn(
            "popularity_contribution",
            F.col("popularity_score") * float(options["cold_popularity_weight"]),
        )
        .withColumn("score", F.col("content_contribution") + F.col("popularity_contribution"))
    )
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return scored.withColumn("rank", F.row_number().over(ranking)).filter(
        F.col("rank") <= int(limit)
    )
