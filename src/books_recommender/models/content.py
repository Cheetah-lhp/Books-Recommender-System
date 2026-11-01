from __future__ import annotations

from pathlib import Path
from typing import Any


def _repeat_tokens(column, repetitions: int):
    from pyspark.sql import functions as F

    return F.flatten(F.array_repeat(column, max(1, repetitions)))


def _weighted_text(books, weights: dict[str, float]):
    from pyspark.sql import functions as F

    # Multiplying every relative weight by two preserves the requested 0.5 increments.
    repeats = {key: max(1, int(round(float(value) * 2))) for key, value in weights.items()}

    def normalize(value):
        return F.regexp_replace(F.lower(value), r"[^\p{L}\p{N}]+", "_")

    title = F.array(F.coalesce(F.col("title"), F.lit("")))
    description = F.array(F.coalesce(F.col("description"), F.lit("")))
    genres = F.transform("genres", lambda value: F.concat(F.lit("genre_"), normalize(value)))
    authors = F.transform("authors", lambda value: F.concat(F.lit("author_"), normalize(value)))
    shelves = F.transform("shelves", lambda value: F.concat(F.lit("shelf_"), normalize(value)))
    decade = F.when(
        F.col("publication_year").isNotNull(),
        (F.floor(F.col("publication_year") / 10) * 10).cast("int").cast("string"),
    ).otherwise(F.lit("unknown"))
    language_decade = F.array(
        F.concat(F.lit("language_"), normalize(F.coalesce("language_code", F.lit("unknown")))),
        F.concat(F.lit("decade_"), decade),
    )
    tokens = F.concat(
        _repeat_tokens(title, repeats["title"]),
        _repeat_tokens(description, repeats["description"]),
        _repeat_tokens(genres, repeats["genres"]),
        _repeat_tokens(authors, repeats["authors"]),
        _repeat_tokens(shelves, repeats["shelves"]),
        _repeat_tokens(language_decade, repeats["language_decade"]),
    )
    return books.withColumn("weighted_text", F.concat_ws(" ", tokens))


def _item_tags(books):
    from pyspark.sql import functions as F

    def normalize(value):
        return F.regexp_replace(F.lower(value), r"[^\p{L}\p{N}]+", "_")

    return (
        books.select("item_idx", F.explode_outer("genres").alias("value"))
        .select("item_idx", F.concat(F.lit("genre:"), normalize("value")).alias("tag"))
        .unionByName(
            books.select("item_idx", F.explode_outer("authors").alias("value")).select(
                "item_idx", F.concat(F.lit("author:"), normalize("value")).alias("tag")
            )
        )
        .unionByName(
            books.select("item_idx", F.explode_outer("shelves").alias("value")).select(
                "item_idx", F.concat(F.lit("shelf:"), normalize("value")).alias("tag")
            )
        )
        .filter(F.col("tag").isNotNull())
        .dropDuplicates()
    )


def train_content(spark, config: dict[str, Any], run_dir: Path) -> None:
    from pyspark.ml import Pipeline
    from pyspark.ml.feature import IDF, HashingTF, Normalizer, RegexTokenizer, StopWordsRemover
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    options = config["models"]["content"]
    processed = Path(config["paths"]["processed"])
    books = spark.read.parquet(str(processed / "books"))
    weighted = _weighted_text(books, options["weights"])
    pipeline = Pipeline(
        stages=[
            RegexTokenizer(inputCol="weighted_text", outputCol="raw_tokens", pattern=r"\s+"),
            StopWordsRemover(inputCol="raw_tokens", outputCol="tokens"),
            HashingTF(
                inputCol="tokens",
                outputCol="tf",
                numFeatures=int(options["num_features"]),
            ),
            IDF(inputCol="tf", outputCol="tfidf", minDocFreq=int(options["min_doc_freq"])),
            Normalizer(inputCol="tfidf", outputCol="features", p=2.0),
        ]
    )
    model = pipeline.fit(weighted)
    model.write().overwrite().save(str(run_dir / "models" / "content" / "pipeline"))
    features = model.transform(weighted).select("item_idx", "work_id", "features")
    features.write.mode("overwrite").parquet(str(run_dir / "models" / "content" / "features"))

    tags = _item_tags(books)
    tags.write.mode("overwrite").parquet(str(run_dir / "models" / "content" / "item_tags"))
    train = spark.read.parquet(str(processed / "interactions")).filter(F.col("split") == "train")
    support = train.groupBy("item_idx").agg(F.count(F.lit(1)).alias("support"))
    tag_window = Window.partitionBy("tag").orderBy(
        F.desc(F.coalesce(F.col("support"), F.lit(0))), F.asc("item_idx")
    )
    tag_index = (
        tags.join(support, "item_idx", "left")
        .withColumn("rank", F.row_number().over(tag_window))
        .filter(F.col("rank") <= int(options["candidates_per_tag"]))
    )
    tag_index.write.mode("overwrite").parquet(str(run_dir / "models" / "content" / "tag_index"))


def content_candidates(spark, run_dir: Path, history, limit: int, max_history: int):
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import DoubleType

    item_tags = spark.read.parquet(str(run_dir / "models" / "content" / "item_tags"))
    tag_index = spark.read.parquet(str(run_dir / "models" / "content" / "tag_index"))
    features = spark.read.parquet(str(run_dir / "models" / "content" / "features"))

    history_window = Window.partitionBy("user_id").orderBy(F.desc("strength"), F.asc("item_idx"))
    seeds = (
        history.withColumn("history_rank", F.row_number().over(history_window))
        .filter(F.col("history_rank") <= int(max_history))
        .select("user_id", F.col("item_idx").alias("seed_idx"), "strength")
    )
    pairs = (
        seeds.join(item_tags.select(F.col("item_idx").alias("seed_idx"), "tag"), "seed_idx")
        .join(tag_index.select("tag", F.col("item_idx").alias("candidate_idx")), "tag")
        .filter(F.col("seed_idx") != F.col("candidate_idx"))
        .groupBy("user_id", "seed_idx", "candidate_idx")
        .agg(F.max("strength").alias("strength"))
    )
    seed_features = features.select(
        F.col("item_idx").alias("seed_idx"), F.col("features").alias("seed_features")
    )
    candidate_features = features.select(
        F.col("item_idx").alias("candidate_idx"), F.col("features").alias("candidate_features")
    )

    @F.udf(DoubleType())
    def cosine(left, right):
        if left is None or right is None:
            return 0.0
        return float(left.dot(right))

    scored = (
        pairs.join(seed_features, "seed_idx")
        .join(candidate_features, "candidate_idx")
        .withColumn("pair_score", cosine("seed_features", "candidate_features") * F.col("strength"))
        .groupBy("user_id", F.col("candidate_idx").alias("item_idx"))
        .agg((F.sum("pair_score") / F.sum("strength")).alias("score"))
    )
    ranking = Window.partitionBy("user_id").orderBy(F.desc("score"), F.asc("item_idx"))
    return scored.withColumn("rank", F.row_number().over(ranking)).filter(
        F.col("rank") <= int(limit)
    )
