from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CORE_FILES = {
    "books": "goodreads_books.json",
    "works": "goodreads_book_works.json",
    "authors": "goodreads_book_authors.json",
    "genres": "goodreads_book_genres_initial.json",
    "book_map": "book_id_map.csv",
    "interactions": "goodreads_interactions.csv",
}


def _resolve_raw(raw_dir: Path, name: str) -> Path | None:
    direct = raw_dir / name
    compressed = raw_dir / f"{name}.gz"
    if direct.exists():
        return direct
    if compressed.exists():
        return compressed
    return None


def validate_raw_files(config: dict[str, Any]) -> dict[str, Path]:
    if config["data"]["source"] == "sample_parquet":
        root = Path(config["paths"]["samples"])
        names = ["books", "works", "authors", "genres", "book_authors_map", "interactions"]
        if config["data"]["split_strategy"] == "temporal_reviews":
            names.append("reviews")
        missing = [name for name in names if not list((root / name).glob("*.parquet"))]
        if missing:
            raise FileNotFoundError(
                f"Missing sample Parquet tables in {root}: {', '.join(missing)}. "
                "Pull samples_data/ from the repository or run process/process_samples.py "
                "on a machine that has the full raw dataset."
            )
        return {name: root / name for name in names}
    raw_dir = Path(config["paths"]["raw"])
    required = dict(CORE_FILES)
    if config["data"]["split_strategy"] == "temporal_reviews":
        required.update(
            {
                "reviews": "goodreads_reviews_dedup.json",
                "user_map": "user_id_map.csv",
            }
        )
    resolved = {key: _resolve_raw(raw_dir, name) for key, name in required.items()}
    missing = [required[key] for key, value in resolved.items() if value is None]
    if missing:
        formatted = "\n  - ".join(missing)
        raise FileNotFoundError(
            f"Missing raw Goodreads files in {raw_dir}:\n  - {formatted}\n"
            "Run process/download.ipynb first. Both plain and .gz JSON files are supported."
        )
    return {key: value for key, value in resolved.items() if value is not None}


def _build_catalog(spark, paths: dict[str, Path], config: dict[str, Any]):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    if config["data"]["source"] == "sample_parquet":
        from books_recommender.data.sample import catalog_sources

        books, works, authors, genres, book_map, raw_interactions = catalog_sources(spark, paths)
    else:
        books = spark.read.json(str(paths["books"])).withColumnRenamed(
            "book_id", "original_book_id"
        )
        works = spark.read.json(str(paths["works"]))
        authors = spark.read.json(str(paths["authors"]))
        genres = spark.read.json(str(paths["genres"])).withColumnRenamed(
            "book_id", "original_book_id"
        )
        book_map = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(str(paths["book_map"]))
            .select(
                F.col("book_id").cast("string").alias("original_book_id"),
                F.col("book_id_csv").cast("int").alias("edition_id"),
            )
        )
        raw_interactions = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(str(paths["interactions"]))
        )
    support = raw_interactions.groupBy(F.col("book_id").cast("int").alias("edition_id")).agg(
        F.count(F.lit(1)).alias("edition_support")
    )

    mapped = (
        books.withColumn("original_book_id", F.col("original_book_id").cast("string"))
        .join(book_map, "original_book_id", "inner")
        .withColumn(
            "work_id",
            F.when(
                F.expr("try_cast(work_id as bigint)") > 0,
                F.col("work_id").cast("string"),
            ).otherwise(F.concat(F.lit("book:"), F.col("original_book_id"))),
        )
        .withColumn(
            "item_idx",
            F.when(F.col("work_id").rlike("^[0-9]+$"), F.col("work_id").cast("int")).otherwise(
                -F.col("edition_id") - F.lit(1)
            ),
        )
    )

    fallback_window = Window.partitionBy("work_id").orderBy(
        F.desc(F.coalesce(F.col("edition_support"), F.lit(0))), F.asc("edition_id")
    )
    fallback = (
        mapped.select("work_id", "item_idx", "edition_id", "original_book_id")
        .join(support, "edition_id", "left")
        .withColumn("rn", F.row_number().over(fallback_window))
        .filter(F.col("rn") == 1)
        .select(
            "work_id",
            "item_idx",
            F.col("edition_id").alias("fallback_edition_id"),
        )
    )

    best_book_map = (
        works.select(
            F.col("work_id").cast("string").alias("work_id"),
            F.col("best_book_id").cast("string").alias("best_original_book_id"),
        )
        .join(
            mapped.select(
                "work_id",
                F.col("original_book_id").alias("best_original_book_id"),
                F.col("edition_id").alias("best_edition_id"),
            ),
            ["work_id", "best_original_book_id"],
            "left",
        )
        .select("work_id", "best_original_book_id", "best_edition_id")
    )
    canonical = (
        fallback.join(best_book_map, "work_id", "left")
        .withColumn(
            "canonical_edition_id",
            F.coalesce(F.col("best_edition_id"), F.col("fallback_edition_id")),
        )
        .withColumn(
            "canonical_book_id",
            F.col("canonical_edition_id"),
        )
        .select(
            "work_id",
            "item_idx",
            "canonical_edition_id",
            F.col("canonical_book_id").cast("long"),
        )
    )

    author_names = (
        mapped.select("edition_id", F.explode_outer("authors").alias("author"))
        .select("edition_id", F.col("author.author_id").cast("string").alias("author_id"))
        .join(authors.select(F.col("author_id").cast("string"), "name"), "author_id", "left")
        .groupBy("edition_id")
        .agg(F.sort_array(F.collect_set(F.coalesce("name", "author_id"))).alias("authors"))
    )

    from pyspark.sql.types import MapType, StructType

    genre_type = genres.schema["genres"].dataType
    if isinstance(genre_type, MapType):
        exploded_genres = genres.select(
            F.col("original_book_id").cast("string"),
            F.explode_outer("genres").alias("genre", "votes"),
        )
    elif isinstance(genre_type, StructType):
        genre_entries = F.array(
            *[
                F.struct(
                    F.lit(field.name).alias("genre"),
                    F.col("genres").getField(field.name).cast("long").alias("votes"),
                )
                for field in genre_type.fields
            ]
        )
        exploded_genres = genres.select(
            F.col("original_book_id").cast("string"),
            F.explode_outer(genre_entries).alias("genre_entry"),
        ).select(
            "original_book_id",
            F.col("genre_entry.genre").alias("genre"),
            F.col("genre_entry.votes").alias("votes"),
        )
    else:
        raise TypeError(f"Unsupported genres schema: {genre_type.simpleString()}")

    genre_names = (
        exploded_genres.filter(F.col("votes").isNotNull())
        .join(book_map, "original_book_id", "inner")
        .groupBy("edition_id")
        .agg(F.sort_array(F.collect_set(F.lower("genre"))).alias("genres"))
    )

    generic_shelves = [value.lower() for value in config["data"]["generic_shelves"]]
    shelf_window = Window.partitionBy("edition_id").orderBy(F.desc("count"), F.asc("shelf"))
    shelf_names = (
        mapped.select("edition_id", F.explode_outer("popular_shelves").alias("shelf_data"))
        .select(
            "edition_id",
            F.lower(F.col("shelf_data.name")).alias("shelf"),
            F.col("shelf_data.count").cast("long").alias("count"),
        )
        .filter(F.col("shelf").isNotNull() & ~F.col("shelf").isin(generic_shelves))
        .withColumn("rn", F.row_number().over(shelf_window))
        .filter(F.col("rn") <= int(config["data"]["max_shelves_per_book"]))
        .groupBy("edition_id")
        .agg(F.collect_list("shelf").alias("shelves"))
    )

    metadata = mapped.select(
        F.col("edition_id").alias("canonical_edition_id"),
        (
            F.regexp_extract("url", r"goodreads\.com/book/show/(\d+)", 1)
            if config["data"]["source"] == "sample_parquet"
            else F.col("original_book_id")
        ).alias("original_book_id"),
        "title",
        "title_without_series",
        "description",
        "language_code",
        "publication_year",
        "image_url",
    )
    canonical_metadata = canonical.join(metadata, "canonical_edition_id", "left")

    canonical_authors = author_names.withColumnRenamed("edition_id", "canonical_edition_id")
    canonical_genres = genre_names.withColumnRenamed("edition_id", "canonical_edition_id")
    canonical_shelves = shelf_names.withColumnRenamed("edition_id", "canonical_edition_id")

    empty_array = F.array().cast("array<string>")
    catalog = (
        canonical_metadata.join(canonical_authors, "canonical_edition_id", "left")
        .join(canonical_genres, "canonical_edition_id", "left")
        .join(canonical_shelves, "canonical_edition_id", "left")
        .select(
            "work_id",
            F.col("item_idx").cast("int"),
            F.col("canonical_book_id").cast("long"),
            "original_book_id",
            F.coalesce("title", "title_without_series", F.lit("")).alias("title"),
            F.coalesce("description", F.lit("")).alias("description"),
            F.coalesce("authors", empty_array).alias("authors"),
            F.coalesce("genres", empty_array).alias("genres"),
            F.coalesce("shelves", empty_array).alias("shelves"),
            F.coalesce("language_code", F.lit("unknown")).alias("language_code"),
            F.expr("try_cast(publication_year as int)").alias("publication_year"),
            "image_url",
        )
        .dropDuplicates(["work_id"])
    )
    edition_to_work = mapped.select("edition_id", "work_id", "item_idx").dropDuplicates(
        ["edition_id"]
    )
    return catalog, edition_to_work, book_map


def _strength_expression(config: dict[str, Any]):
    from pyspark.sql import functions as F

    signals = config["signals"]
    bonus = F.lit(0.0)
    for rating, value in signals["rating_bonus"].items():
        bonus = F.when(F.col("rating") == int(rating), float(value)).otherwise(bonus)
    return (
        F.lit(float(signals["base"]))
        + F.coalesce(F.col("is_read").cast("int"), F.lit(0)) * F.lit(float(signals["read"]))
        + F.coalesce(F.col("is_reviewed").cast("int"), F.lit(0)) * F.lit(float(signals["reviewed"]))
        + bonus
    )


def _build_interactions(
    spark,
    paths: dict[str, Path],
    edition_to_work,
    book_map,
    config: dict[str, Any],
):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    if config["data"]["source"] == "sample_parquet":
        from books_recommender.data.sample import interaction_source

        interactions = interaction_source(spark, paths, edition_to_work, config)
    elif config["data"]["split_strategy"] == "temporal_reviews":
        user_map = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(str(paths["user_map"]))
            .select(
                F.col("user_id").cast("string").alias("hashed_user_id"),
                F.col("user_id_csv").cast("int").alias("user_id"),
            )
        )
        reviews = (
            spark.read.json(str(paths["reviews"]))
            .withColumnRenamed("user_id", "hashed_user_id")
            .withColumnRenamed("book_id", "original_book_id")
            .join(user_map, "hashed_user_id", "inner")
            .join(
                book_map.select(
                    F.col("original_book_id").cast("string"),
                    F.col("edition_id"),
                ),
                "original_book_id",
                "inner",
            )
            .join(edition_to_work, "edition_id", "inner")
            .select(
                "user_id",
                "work_id",
                "item_idx",
                F.col("rating").cast("int"),
                F.lit(True).alias("is_read"),
                F.lit(True).alias("is_reviewed"),
                F.to_timestamp(
                    F.regexp_replace("date_added", r"^\w+ ", ""),
                    "MMM dd HH:mm:ss Z yyyy",
                ).alias("event_time"),
            )
        )
        latest_window = Window.partitionBy("user_id", "item_idx").orderBy(
            F.desc_nulls_last("event_time")
        )
        interactions = reviews.withColumn("edition_rn", F.row_number().over(latest_window)).filter(
            F.col("edition_rn") == 1
        )
    else:
        interactions = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(str(paths["interactions"]))
            .select(
                F.col("user_id").cast("int"),
                F.col("book_id").cast("int").alias("edition_id"),
                F.col("rating").cast("int"),
                F.col("is_read").cast("boolean"),
                F.col("is_reviewed").cast("boolean"),
            )
            .join(edition_to_work, "edition_id", "inner")
            .groupBy("user_id", "work_id", "item_idx")
            .agg(
                F.max("rating").alias("rating"),
                F.max(F.col("is_read").cast("int")).cast("boolean").alias("is_read"),
                F.max(F.col("is_reviewed").cast("int")).cast("boolean").alias("is_reviewed"),
            )
            .withColumn("event_time", F.lit(None).cast("timestamp"))
        )

    excluded = [int(value) for value in config["signals"]["excluded_ratings"]]
    interactions = interactions.filter(
        ~F.coalesce(F.col("rating").isin(excluded), F.lit(False))
    ).withColumn("strength", _strength_expression(config).cast("float"))

    eligible = Window.partitionBy("user_id")
    interactions = interactions.withColumn(
        "user_positives", F.count(F.lit(1)).over(eligible)
    ).filter(F.col("user_positives") >= int(config["data"]["min_user_positives"]))

    sample_users = config["data"].get("sample_users")
    if config["mode"] == "sample" and sample_users:
        selected_users = (
            interactions.select("user_id")
            .distinct()
            .withColumn("sample_hash", F.xxhash64("user_id", F.lit(int(config["seed"]))))
            .orderBy("sample_hash", "user_id")
            .limit(int(sample_users))
            .select("user_id")
        )
        interactions = interactions.join(F.broadcast(selected_users), "user_id", "inner")

    if config["data"]["split_strategy"] == "temporal_reviews":
        split_window = Window.partitionBy("user_id").orderBy(
            F.desc_nulls_last("event_time"), F.asc("item_idx")
        )
    else:
        split_window = Window.partitionBy("user_id").orderBy(
            F.xxhash64("user_id", "item_idx", F.lit(int(config["seed"]))), F.asc("item_idx")
        )
    return (
        interactions.withColumn("split_rank", F.row_number().over(split_window))
        .withColumn(
            "split",
            F.when(F.col("split_rank") == 1, F.lit("test"))
            .when(F.col("split_rank") == 2, F.lit("validation"))
            .otherwise(F.lit("train")),
        )
        .select(
            "user_id",
            "work_id",
            F.col("item_idx").cast("int"),
            "rating",
            "is_read",
            "is_reviewed",
            "strength",
            "event_time",
            "split",
        )
    )


def prepare_dataset(spark, config: dict[str, Any]) -> dict[str, Any]:
    paths = validate_raw_files(config)
    processed = Path(config["paths"]["processed"])
    processed.mkdir(parents=True, exist_ok=True)

    catalog, edition_to_work, book_map = _build_catalog(spark, paths, config)
    interactions = _build_interactions(spark, paths, edition_to_work, book_map, config)
    if not interactions.limit(1).count():
        raise ValueError("No eligible positive interactions; check the source and user threshold.")

    catalog.write.mode("overwrite").parquet(str(processed / "books"))
    edition_to_work.write.mode("overwrite").parquet(str(processed / "edition_to_work"))
    interactions.repartition(int(config["spark"]["shuffle_partitions"]), "user_id").write.mode(
        "overwrite"
    ).partitionBy("split").parquet(str(processed / "interactions"))

    prepared_books = spark.read.parquet(str(processed / "books"))
    prepared_interactions = spark.read.parquet(str(processed / "interactions"))

    manifest = {
        "source": config["data"]["source"],
        "book_id_namespace": "book_id_csv",
        "mode": config["mode"],
        "seed": int(config["seed"]),
        "split_strategy": config["data"]["split_strategy"],
        "books": prepared_books.count(),
        "interactions": prepared_interactions.count(),
        "users": prepared_interactions.select("user_id").distinct().count(),
        "paths": {key: str(value) for key, value in paths.items()},
    }
    with (processed / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    return manifest
