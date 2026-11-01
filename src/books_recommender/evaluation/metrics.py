from __future__ import annotations

import math
from collections.abc import Iterable


def precision_at_k(recommended: Iterable[int], relevant: set[int], k: int) -> float:
    items = list(recommended)[:k]
    return sum(item in relevant for item in items) / k if k else 0.0


def recall_at_k(recommended: Iterable[int], relevant: set[int], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(item in relevant for item in list(recommended)[:k]) / len(relevant)


def ndcg_at_k(recommended: Iterable[int], relevant: set[int], k: int) -> float:
    gains = [
        1.0 / math.log2(index + 2)
        for index, item in enumerate(list(recommended)[:k])
        if item in relevant
    ]
    ideal = sum(1.0 / math.log2(index + 2) for index in range(min(k, len(relevant))))
    return sum(gains) / ideal if ideal else 0.0


def average_precision_at_k(recommended: Iterable[int], relevant: set[int], k: int) -> float:
    if not relevant:
        return 0.0
    hits = 0
    total = 0.0
    for rank, item in enumerate(list(recommended)[:k], start=1):
        if item in relevant:
            hits += 1
            total += hits / rank
    return total / min(k, len(relevant))


def reciprocal_rank(recommended: Iterable[int], relevant: set[int], k: int) -> float:
    for rank, item in enumerate(list(recommended)[:k], start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def spark_ranking_metrics(predictions, truth, ks: list[int]) -> dict[str, float]:
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    truth = truth.select("user_id", "item_idx").dropDuplicates().cache()
    users = truth.select("user_id").distinct()
    truth_counts = truth.groupBy("user_id").agg(F.count(F.lit(1)).alias("truth_count"))
    results: dict[str, float] = {}

    for k in sorted(set(int(value) for value in ks)):
        top = predictions.filter(F.col("rank") <= k).select("user_id", "item_idx", "rank")
        marked = (
            top.join(truth.withColumn("hit", F.lit(1)), ["user_id", "item_idx"], "left")
            .fillna(0, subset=["hit"])
            .withColumn("discounted_gain", F.col("hit") / F.log2(F.col("rank") + F.lit(1)))
        )
        cumulative = (
            Window.partitionBy("user_id")
            .orderBy("rank")
            .rowsBetween(Window.unboundedPreceding, Window.currentRow)
        )
        marked = marked.withColumn("hits_so_far", F.sum("hit").over(cumulative)).withColumn(
            "ap_term",
            F.when(F.col("hit") == 1, F.col("hits_so_far") / F.col("rank")).otherwise(0.0),
        )
        per_user = marked.groupBy("user_id").agg(
            F.sum("hit").alias("hits"),
            F.sum("discounted_gain").alias("dcg"),
            F.sum("ap_term").alias("ap_sum"),
            F.min(F.when(F.col("hit") == 1, F.col("rank"))).alias("first_hit_rank"),
        )
        complete = (
            users.join(truth_counts, "user_id")
            .join(per_user, "user_id", "left")
            .fillna(0.0, subset=["hits", "dcg", "ap_sum"])
            .withColumn("precision", F.col("hits") / F.lit(float(k)))
            .withColumn("recall", F.col("hits") / F.col("truth_count"))
            .withColumn(
                "ideal_dcg",
                F.expr(
                    f"aggregate(sequence(1, cast(least({k}, truth_count) as int)), 0D, "
                    "(acc, x) -> acc + 1D / log2(x + 1D))"
                ),
            )
            .withColumn(
                "ndcg",
                F.when(F.col("ideal_dcg") > 0, F.col("dcg") / F.col("ideal_dcg")).otherwise(0.0),
            )
            .withColumn("map", F.col("ap_sum") / F.least(F.lit(k), F.col("truth_count")))
            .withColumn(
                "mrr",
                F.when(
                    F.col("first_hit_rank").isNotNull(), 1.0 / F.col("first_hit_rank")
                ).otherwise(0.0),
            )
            .withColumn("hit_rate", F.when(F.col("hits") > 0, 1.0).otherwise(0.0))
        )
        row = complete.agg(
            F.avg("precision").alias("precision"),
            F.avg("recall").alias("recall"),
            F.avg("ndcg").alias("ndcg"),
            F.avg("map").alias("map"),
            F.avg("mrr").alias("mrr"),
            F.avg("hit_rate").alias("hit_rate"),
        ).first()
        for metric in ("precision", "recall", "ndcg", "map", "mrr", "hit_rate"):
            results[f"{metric}@{k}"] = float(row[metric] or 0.0)
    truth.unpersist()
    return results


def catalog_metrics(predictions, train, books, k: int) -> dict[str, float]:
    from pyspark.sql import functions as F

    top = predictions.filter(F.col("rank") <= int(k)).select("user_id", "item_idx", "rank")
    catalog_size = books.select("item_idx").distinct().count()
    coverage = top.select("item_idx").distinct().count() / catalog_size if catalog_size else 0.0

    counts = train.groupBy("item_idx").agg(F.count(F.lit(1)).alias("item_count"))
    total = train.count()
    novelty_row = (
        top.join(counts, "item_idx", "left")
        .fillna(0, subset=["item_count"])
        .agg(
            F.avg(
                -F.log2(
                    (F.col("item_count") + F.lit(1.0)) / F.lit(float(total + max(catalog_size, 1)))
                )
            ).alias("novelty")
        )
        .first()
    )

    ranked_genres = top.join(books.select("item_idx", "genres"), "item_idx", "left")
    left = ranked_genres.alias("left")
    right = ranked_genres.alias("right")
    pairs = left.join(
        right,
        (F.col("left.user_id") == F.col("right.user_id"))
        & (F.col("left.rank") < F.col("right.rank")),
        "inner",
    )
    diversity_row = (
        pairs.select(
            F.when(
                F.size(F.array_union(F.col("left.genres"), F.col("right.genres"))) > 0,
                1.0
                - F.size(F.array_intersect(F.col("left.genres"), F.col("right.genres")))
                / F.size(F.array_union(F.col("left.genres"), F.col("right.genres"))),
            )
            .otherwise(0.0)
            .alias("distance")
        )
        .agg(F.avg("distance").alias("diversity"))
        .first()
    )

    return {
        f"catalog_coverage@{k}": float(coverage),
        f"novelty@{k}": float(novelty_row["novelty"] or 0.0),
        f"genre_diversity@{k}": float(diversity_row["diversity"] or 0.0),
    }
