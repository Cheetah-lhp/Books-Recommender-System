from __future__ import annotations

from pathlib import Path
from typing import Any

from books_recommender.artifacts import update_manifest, write_json
from books_recommender.evaluation.metrics import catalog_metrics, spark_ranking_metrics
from books_recommender.models.als import als_candidates, load_als
from books_recommender.models.content import content_candidates
from books_recommender.models.hybrid import exclude_seen_and_rank, hybrid_candidates
from books_recommender.models.item_item import item_item_candidates
from books_recommender.models.popularity import popularity_candidates


def _slice_recall(predictions, truth, train, k: int) -> dict[str, float]:
    from pyspark.sql import functions as F

    top = predictions.filter(F.col("rank") <= int(k)).select("user_id", "item_idx")
    hits = top.join(truth.select("user_id", "item_idx"), ["user_id", "item_idx"]).withColumn(
        "hit", F.lit(1)
    )
    user_activity = (
        train.groupBy("user_id")
        .agg(F.count(F.lit(1)).alias("activity"))
        .withColumn(
            "bucket",
            F.when(F.col("activity") < 10, "5-9")
            .when(F.col("activity") < 50, "10-49")
            .otherwise("50+"),
        )
    )
    user_truth = (
        truth.join(user_activity, "user_id").groupBy("bucket").agg(F.count(F.lit(1)).alias("truth"))
    )
    user_hits = (
        hits.join(user_activity, "user_id").groupBy("bucket").agg(F.count(F.lit(1)).alias("hits"))
    )
    user_rows = user_truth.join(user_hits, "bucket", "left").fillna(0, subset=["hits"]).collect()

    item_popularity = train.groupBy("item_idx").agg(F.count(F.lit(1)).alias("popularity"))
    item_truth = (
        truth.join(item_popularity, "item_idx", "left")
        .fillna(0, subset=["popularity"])
        .withColumn(
            "bucket",
            F.when(F.col("popularity") < 5, "0-4")
            .when(F.col("popularity") < 50, "5-49")
            .otherwise("50+"),
        )
    )
    item_totals = item_truth.groupBy("bucket").agg(F.count(F.lit(1)).alias("truth"))
    item_hits = (
        hits.join(item_truth.select("user_id", "item_idx", "bucket"), ["user_id", "item_idx"])
        .groupBy("bucket")
        .agg(F.count(F.lit(1)).alias("hits"))
    )
    item_rows = item_totals.join(item_hits, "bucket", "left").fillna(0, subset=["hits"]).collect()

    result = {
        f"user_activity/{row['bucket']}/recall@{k}": float(row["hits"] / row["truth"])
        for row in user_rows
        if row["truth"]
    }
    result.update(
        {
            f"item_popularity/{row['bucket']}/recall@{k}": float(row["hits"] / row["truth"])
            for row in item_rows
            if row["truth"]
        }
    )
    return result


def evaluate_run(spark, config: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    from pyspark.sql import functions as F

    processed = Path(config["paths"]["processed"])
    interactions = spark.read.parquet(str(processed / "interactions")).cache()
    books = spark.read.parquet(str(processed / "books")).cache()
    train = interactions.filter(F.col("split") == "train").cache()
    split_name = config["evaluation"]["split"]
    truth = interactions.filter(F.col("split") == split_name).select("user_id", "item_idx").cache()
    users = truth.select("user_id").distinct().cache()
    ks = [int(value) for value in config["evaluation"]["ks"]]
    max_k = max(ks)
    prediction_dir = run_dir / "evaluation" / "predictions"
    predictions: dict[str, Any] = {}

    popularity_path = run_dir / "models" / "popularity" / "global"
    if popularity_path.exists():
        popularity = popularity_candidates(
            spark,
            run_dir,
            users,
            max(max_k, int(config["models"]["hybrid"]["popularity_candidates"])),
        )
        predictions["popularity"] = exclude_seen_and_rank(popularity, train, max_k)

    item_path = run_dir / "models" / "item_item" / "neighbors"
    if item_path.exists():
        item_candidates = item_item_candidates(spark, run_dir, train, max_k + 100)
        predictions["item_item"] = exclude_seen_and_rank(item_candidates, train, max_k)

    als_path = run_dir / "models" / "als" / "model"
    als_for_hybrid = None
    if als_path.exists():
        model = load_als(run_dir)
        als_for_hybrid = exclude_seen_and_rank(
            als_candidates(model, users, int(config["models"]["als"]["candidates"]) + 100),
            train,
            int(config["models"]["als"]["candidates"]),
        ).cache()
        predictions["als"] = als_for_hybrid.filter(F.col("rank") <= max_k)

    content_path = run_dir / "models" / "content" / "features"
    content_for_hybrid = None
    if content_path.exists():
        content_for_hybrid = exclude_seen_and_rank(
            content_candidates(
                spark,
                run_dir,
                train.join(users, "user_id", "inner"),
                int(config["models"]["content"]["candidates"]) + 100,
                int(config["models"]["content"]["max_history"]),
            ),
            train,
            int(config["models"]["content"]["candidates"]),
        ).cache()
        predictions["content"] = content_for_hybrid.filter(F.col("rank") <= max_k)

    popularity_for_hybrid = None
    if popularity_path.exists():
        popularity_for_hybrid = exclude_seen_and_rank(
            popularity_candidates(
                spark,
                run_dir,
                users,
                int(config["models"]["hybrid"]["popularity_candidates"]) + 100,
            ),
            train,
            int(config["models"]["hybrid"]["popularity_candidates"]),
        ).cache()

    if (
        als_for_hybrid is not None
        and content_for_hybrid is not None
        and popularity_for_hybrid is not None
    ):
        predictions["hybrid"] = hybrid_candidates(
            als_for_hybrid,
            content_for_hybrid,
            popularity_for_hybrid,
            config,
            max(int(config["models"]["als"]["candidates"]), max_k),
        ).cache()

    report: dict[str, Any] = {
        "split": split_name,
        "users": users.count(),
        "truth_items": truth.count(),
        "models": {},
    }
    for name, frame in predictions.items():
        frame.write.mode("overwrite").parquet(str(prediction_dir / name))
        metrics = spark_ranking_metrics(frame, truth, ks)
        metrics.update(catalog_metrics(frame, train, books, max_k))
        metrics.update(_slice_recall(frame, truth, train, max_k))
        if name == "hybrid":
            candidate_hits = (
                frame.select("user_id", "item_idx").join(truth, ["user_id", "item_idx"]).count()
            )
            metrics["candidate_recall"] = (
                float(candidate_hits / report["truth_items"]) if report["truth_items"] else 0.0
            )
        report["models"][name] = metrics

    write_json(run_dir / "metrics.json", report)
    update_manifest(run_dir, status="evaluated", metrics="metrics.json")
    for frame in (als_for_hybrid, content_for_hybrid, popularity_for_hybrid):
        if frame is not None:
            frame.unpersist()
    users.unpersist()
    truth.unpersist()
    train.unpersist()
    books.unpersist()
    interactions.unpersist()
    return report
