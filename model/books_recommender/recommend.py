from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from books_recommender.models.als import als_candidates, load_als
from books_recommender.models.content import content_candidates
from books_recommender.models.hybrid import (
    cold_hybrid_candidates,
    exclude_seen_and_rank,
    hybrid_candidates,
)
from books_recommender.models.popularity import popularity_candidates


def _genre_candidates(spark, run_dir: Path, user_id: int, genres: list[str], limit: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    normalized = [re.sub(r"[^\w]+", "_", value.lower()).strip("_") for value in genres]
    tags = [f"genre:{value}" for value in normalized if value]
    index = spark.read.parquet(str(run_dir / "models" / "content" / "tag_index"))
    candidates = (
        index.filter(F.col("tag").isin(tags))
        .groupBy("item_idx")
        .agg(F.sum(1.0 / F.col("rank")).alias("score"))
        .withColumn("user_id", F.lit(int(user_id)))
    )
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return candidates.withColumn("rank", F.row_number().over(ranking)).filter(
        F.col("rank") <= int(limit)
    )


def recommend(
    spark,
    config: dict[str, Any],
    run_dir: Path,
    *,
    user_id: int | None = None,
    seed_book_ids: list[int] | None = None,
    genres: list[str] | None = None,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    from pyspark.sql import functions as F

    processed = Path(config["paths"]["processed"])
    books = spark.read.parquet(str(processed / "books"))
    interactions = spark.read.parquet(str(processed / "interactions"))
    train = interactions.filter(F.col("split") == "train")
    effective_user = int(user_id) if user_id is not None else -1
    known_history = train.filter(F.col("user_id") == effective_user).select(
        "user_id", "item_idx", "strength"
    )
    is_known = user_id is not None and known_history.limit(1).count() > 0

    history = known_history
    if not is_known and seed_book_ids:
        history = (
            spark.read.parquet(str(processed / "edition_to_work"))
            .filter(F.col("edition_id").isin([int(value) for value in seed_book_ids]))
            .select("item_idx")
            .distinct()
            .withColumn("user_id", F.lit(effective_user))
            .withColumn("strength", F.lit(1.0))
            .select("user_id", "item_idx", "strength")
        )
    users = spark.createDataFrame([(effective_user,)], ["user_id"])
    popularity = popularity_candidates(
        spark,
        run_dir,
        users,
        max(top_k, int(config["models"]["hybrid"]["popularity_candidates"])),
    )

    result = None
    if is_known:
        als = als_candidates(
            load_als(run_dir), users, int(config["models"]["als"]["candidates"]) + 100
        )
        als = exclude_seen_and_rank(als, history, int(config["models"]["als"]["candidates"]))
        content = content_candidates(
            spark,
            run_dir,
            history,
            int(config["models"]["content"]["candidates"]) + 100,
            int(config["models"]["content"]["max_history"]),
        )
        content = exclude_seen_and_rank(
            content, history, int(config["models"]["content"]["candidates"])
        )
        popularity = exclude_seen_and_rank(
            popularity, history, int(config["models"]["hybrid"]["popularity_candidates"])
        )
        result = hybrid_candidates(als, content, popularity, config, top_k)
    elif history.limit(1).count() > 0 or genres:
        if history.limit(1).count() > 0:
            content = content_candidates(
                spark,
                run_dir,
                history,
                int(config["models"]["content"]["candidates"]),
                int(config["models"]["content"]["max_history"]),
            )
            content = exclude_seen_and_rank(
                content, history, int(config["models"]["content"]["candidates"])
            )
        else:
            content = _genre_candidates(
                spark,
                run_dir,
                effective_user,
                genres or [],
                int(config["models"]["content"]["candidates"]),
            )
        popularity = exclude_seen_and_rank(
            popularity, history, int(config["models"]["hybrid"]["popularity_candidates"])
        )
        result = cold_hybrid_candidates(content, popularity, config, top_k)
    else:
        from pyspark.sql import Window

        ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
        result = (
            popularity.withColumn("popularity_score", F.lit(1.0))
            .withColumn("als_score", F.lit(0.0))
            .withColumn("content_score", F.lit(0.0))
            .withColumn("als_contribution", F.lit(0.0))
            .withColumn("content_contribution", F.lit(0.0))
            .withColumn("popularity_contribution", F.col("score"))
            .drop("rank")
            .withColumn("rank", F.row_number().over(ranking))
            .filter(F.col("rank") <= int(top_k))
        )

    enriched = (
        result.join(
            books.select("item_idx", "work_id", "canonical_book_id", "title"),
            "item_idx",
            "inner",
        )
        .orderBy("rank")
        .select(
            "rank",
            "work_id",
            "canonical_book_id",
            "title",
            F.col("score").cast("double"),
            F.coalesce("als_contribution", F.lit(0.0)).alias("als"),
            F.coalesce("content_contribution", F.lit(0.0)).alias("content"),
            F.coalesce("popularity_contribution", F.lit(0.0)).alias("popularity"),
        )
    )
    return [row.asDict(recursive=True) for row in enriched.collect()]
