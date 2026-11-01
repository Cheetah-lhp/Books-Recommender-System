"""Read the upstream ETL's Parquet tables without modifying their contents."""

from __future__ import annotations


def catalog_sources(spark, paths):
    from pyspark.sql import functions as F

    # The upstream ETL replaced Goodreads IDs with book_id_csv. Use those keys
    # throughout this adapter; the URL's Goodreads ID is optional provenance only.
    source = spark.read.parquet(str(paths["books"]))
    book_map = source.select(
        F.col("book_id").cast("string").alias("original_book_id"),
        F.col("book_id").cast("int").alias("edition_id"),
    )
    authors_map = (
        spark.read.parquet(str(paths["book_authors_map"]))
        .groupBy("book_id")
        .agg(F.collect_list(F.struct("author_id", "role")).alias("authors"))
    )
    books = (
        source.join(authors_map, "book_id", "left")
        .withColumn("popular_shelves", F.array().cast("array<struct<name:string,count:string>>"))
        .withColumnRenamed("book_id", "original_book_id")
        .withColumn("original_book_id", F.col("original_book_id").cast("string"))
    )
    # Adapt to the raw reader's genre map schema, retaining only positive votes
    # (the upstream source also contains sparse/null entries).
    genres = (
        spark.read.parquet(str(paths["genres"]))
        .filter(F.col("votes") > 0)
        .groupBy("book_id")
        .agg(F.collect_set(F.struct(F.col("genres").alias("key"), "votes")).alias("entries"))
        .select(
            F.col("book_id").cast("string").alias("original_book_id"),
            F.map_from_entries("entries").alias("genres"),
        )
    )
    works = spark.read.parquet(str(paths["works"]))
    # Auxiliary upstream tables are not sampled: restrict them before further joins.
    works = works.join(source.select("work_id").distinct(), "work_id", "left_semi")
    authors = spark.read.parquet(str(paths["authors"]))
    authors = authors.join(
        spark.read.parquet(str(paths["book_authors_map"])).select("author_id").distinct(),
        "author_id",
        "left_semi",
    )
    interactions = spark.read.parquet(str(paths["interactions"]))
    return books, works, authors, genres, book_map, interactions


def interaction_source(spark, paths, edition_to_work, config):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    if config["data"]["split_strategy"] == "temporal_reviews":
        source = spark.read.parquet(str(paths["reviews"]))
        # Remove the English weekday prefix: Spark's modern date parser does not
        # support EEE, while numeric timestamps retain the actual UTC offset.
        source = (
            source.withColumn(
                "event_time",
                F.to_timestamp(
                    F.regexp_replace("date_added", r"^\w+ ", ""), "MMM dd HH:mm:ss Z yyyy"
                ),
            )
            .withColumn("is_read", F.lit(True))
            .withColumn("is_reviewed", F.lit(True))
        )
    else:
        source = spark.read.parquet(str(paths["interactions"])).withColumn(
            "event_time", F.lit(None).cast("timestamp")
        )
    source = source.select(
        F.col("user_id").cast("int"),
        F.col("book_id").cast("int").alias("edition_id"),
        F.col("rating").cast("int"),
        F.col("is_read").cast("boolean"),
        F.col("is_reviewed").cast("boolean"),
        "event_time",
    ).join(edition_to_work.select("edition_id", "work_id", "item_idx"), "edition_id")
    if config["data"]["split_strategy"] == "temporal_reviews":
        window = Window.partitionBy("user_id", "item_idx").orderBy(
            F.desc_nulls_last("event_time"), F.desc("rating")
        )
        return source.withColumn("rn", F.row_number().over(window)).filter("rn = 1")
    return source.groupBy("user_id", "work_id", "item_idx").agg(
        F.max("rating").alias("rating"),
        F.max(F.col("is_read").cast("int")).cast("boolean").alias("is_read"),
        F.max(F.col("is_reviewed").cast("int")).cast("boolean").alias("is_reviewed"),
        F.max("event_time").alias("event_time"),
    )
