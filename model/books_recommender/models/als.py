from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from books_recommender.artifacts import write_json


def _fit(train, options: dict[str, Any], seed: int):
    from pyspark.ml.recommendation import ALS

    estimator = ALS(
        userCol="user_id",
        itemCol="item_idx",
        ratingCol="strength",
        implicitPrefs=True,
        coldStartStrategy="drop",
        nonnegative=True,
        rank=int(options["rank"]),
        maxIter=int(options["max_iter"]),
        regParam=float(options["reg_param"]),
        alpha=float(options["alpha"]),
        seed=int(seed),
    )
    return estimator.fit(train.select("user_id", "item_idx", "strength"))


def _validation_recall(model, train, validation, k: int) -> float:
    from pyspark.sql import functions as F

    users = validation.select("user_id").distinct()
    candidates = als_candidates(model, users, k + 100)
    seen = train.select("user_id", "item_idx").dropDuplicates()
    predictions = candidates.join(seen, ["user_id", "item_idx"], "left_anti")
    top = predictions.groupBy("user_id").agg(
        F.slice(
            F.sort_array(F.collect_list(F.struct(F.col("rank"), F.col("item_idx")))), 1, k
        ).alias("items")
    )
    predicted = top.select("user_id", F.explode("items.item_idx").alias("item_idx"))
    hits = predicted.join(validation.select("user_id", "item_idx"), ["user_id", "item_idx"]).count()
    truth = validation.count()
    return float(hits / truth) if truth else 0.0


def train_als(spark, config: dict[str, Any], run_dir: Path) -> None:
    from pyspark.sql import functions as F

    options = dict(config["models"]["als"])
    interactions = spark.read.parquet(str(Path(config["paths"]["processed"]) / "interactions"))
    train = interactions.filter(F.col("split") == "train").cache()
    validation = interactions.filter(F.col("split") == "validation").cache()
    tuning_results: list[dict[str, Any]] = []

    tune = options.get("tune", {})
    if tune.get("enabled"):
        best_score = -1.0
        best_params: dict[str, Any] | None = None
        for rank, reg_param, alpha in itertools.product(
            tune["ranks"], tune["reg_params"], tune["alphas"]
        ):
            candidate_options = dict(options)
            candidate_options.update(rank=rank, reg_param=reg_param, alpha=alpha)
            candidate_model = _fit(train, candidate_options, int(config["seed"]))
            recall = _validation_recall(candidate_model, train, validation, k=20)
            result = {"rank": rank, "reg_param": reg_param, "alpha": alpha, "recall_at_20": recall}
            tuning_results.append(result)
            if recall > best_score:
                best_score, best_params = recall, result
        if best_params:
            options.update(
                rank=best_params["rank"],
                reg_param=best_params["reg_param"],
                alpha=best_params["alpha"],
            )
        write_json(run_dir / "models" / "als" / "tuning.json", tuning_results)

    model = _fit(train, options, int(config["seed"]))
    model.write().overwrite().save(str(run_dir / "models" / "als" / "model"))
    write_json(
        run_dir / "models" / "als" / "parameters.json",
        {key: options[key] for key in ("rank", "max_iter", "reg_param", "alpha")},
    )
    train.unpersist()
    validation.unpersist()


def load_als(run_dir: Path):
    from pyspark.ml.recommendation import ALSModel

    return ALSModel.load(str(run_dir / "models" / "als" / "model"))


def als_candidates(model, users, limit: int):
    from pyspark.sql import functions as F

    recommendations = model.recommendForUserSubset(users.select("user_id").distinct(), int(limit))
    return recommendations.select(
        "user_id", F.posexplode("recommendations").alias("position", "rec")
    ).select(
        "user_id",
        F.col("rec.item_idx").alias("item_idx"),
        F.col("rec.rating").cast("double").alias("score"),
        (F.col("position") + F.lit(1)).alias("rank"),
    )
