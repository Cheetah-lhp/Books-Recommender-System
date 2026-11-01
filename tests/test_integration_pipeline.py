from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest

from books_recommender.config import load_config
from books_recommender.data.prepare import prepare_dataset
from books_recommender.evaluation.evaluator import evaluate_run
from books_recommender.recommend import recommend
from books_recommender.serving.runtime import DemoRecommender
from books_recommender.spark import create_spark
from books_recommender.training import train_models

pytest.importorskip("pyspark")

pytestmark = pytest.mark.skipif(
    os.name == "nt",
    reason="PySpark local Hadoop writes need winutils on Windows; run this test in Docker/WSL",
)


def _json_lines(path: Path, rows: list[dict]):
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")


def _fixture(raw: Path):
    raw.mkdir(parents=True)
    authors = [{"author_id": "1", "name": "Test Author"}]
    books = []
    works = []
    genres = []
    for item in range(1, 8):
        work_id = 101 if item == 7 else 100 + item
        books.append(
            {
                "book_id": str(1000 + item),
                "work_id": str(work_id),
                "title": f"Book {item}",
                "title_without_series": f"Book {item}",
                "description": f"shared fantasy adventure topic {item}",
                "authors": [{"author_id": "1", "role": ""}],
                "popular_shelves": [
                    {"name": "fantasy", "count": "10"},
                    {"name": "to-read", "count": "100"},
                ],
                "language_code": "eng",
                "publication_year": "2010",
                "image_url": "",
                "url": f"https://www.goodreads.com/book/show/{1000 + item}",
            }
        )
        if item <= 6:
            works.append({"work_id": str(work_id), "best_book_id": str(1000 + item)})
        genres.append({"book_id": str(1000 + item), "genres": {"fantasy": 10}})
    _json_lines(raw / "goodreads_books.json", books)
    _json_lines(raw / "goodreads_book_works.json", works)
    _json_lines(raw / "goodreads_book_authors.json", authors)
    _json_lines(raw / "goodreads_book_genres_initial.json", genres)
    with (raw / "book_id_map.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["book_id", "book_id_csv"])
        writer.writerows((1000 + item, item) for item in range(1, 8))
    with (raw / "goodreads_interactions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "book_id", "is_read", "rating", "is_reviewed"])
        for user in range(1, 7):
            for item in range(1, 8):
                writer.writerow([user, item, 1, 3 + ((user + item) % 3), int(item % 2 == 0)])


def _sample_fixture(raw: Path, output: Path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    def write(name, rows):
        destination = output / name
        destination.mkdir(parents=True)
        pq.write_table(pa.Table.from_pylist(rows), destination / "part-00000.parquet")

    def read(name):
        return [json.loads(line) for line in (raw / name).read_text().splitlines()]

    source_books = read("goodreads_books.json")
    write(
        "books",
        [
            {
                **{k: v for k, v in book.items() if k not in {"authors", "popular_shelves"}},
                "book_id": int(book["book_id"]) - 1000,
                "publication_year": "" if i == 0 else book["publication_year"],
            }
            for i, book in enumerate(source_books)
        ],
    )
    write("authors", read("goodreads_book_authors.json"))
    write(
        "book_authors_map",
        [
            {"book_id": int(book["book_id"]) - 1000, "author_id": "1", "role": ""}
            for book in source_books
        ],
    )
    write(
        "works",
        [
            {
                "work_id": row["work_id"],
                "best_book_id": 9999
                if row["work_id"] == "102"
                else int(row["best_book_id"]) - 1000,
            }
            for row in read("goodreads_book_works.json")
        ],
    )
    write(
        "genres",
        [
            {"book_id": int(book["book_id"]) - 1000, "genres": genre, "votes": votes}
            for book in source_books
            for genre, votes in [("fantasy, paranormal", 10), ("unused", 0)]
        ],
    )
    with (raw / "goodreads_interactions.csv").open() as handle:
        write(
            "interactions", [{k: int(v) for k, v in row.items()} for row in csv.DictReader(handle)]
        )


@pytest.mark.integration
@pytest.mark.parametrize("source", ["raw_goodreads", "sample_parquet"])
def test_end_to_end(tmp_path, source):
    raw = tmp_path / "raw"
    _fixture(raw)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
mode: sample
seed: 42
paths:
  raw: {raw.as_posix()}
  processed: {(tmp_path / "processed").as_posix()}
  artifacts: {(tmp_path / "artifacts").as_posix()}
  checkpoints: {(tmp_path / "checkpoints").as_posix()}
spark: {{app_name: test, master: 'local[1]', driver_memory: 1g, shuffle_partitions: 2}}
data:
  sample_users: 100
  min_user_positives: 5
  split_strategy: per_user
  generic_shelves: [to-read]
  max_shelves_per_book: 5
models:
  popularity: {{top_n: 20}}
  item_item: {{max_history: 10, min_cooccurrence: 1, top_n: 10}}
  als: {{rank: 4, max_iter: 2, reg_param: 0.1, alpha: 5, candidates: 10, tune: {{enabled: false}}}}
  content:
    num_features: 64
    min_doc_freq: 1
    max_history: 5
    candidates_per_tag: 20
    candidates: 10
    weights: {{title: 2, description: 1, genres: 3, authors: 2, shelves: 1.5, language_decade: 0.5}}
  hybrid:
    als_weight: 0.7
    content_weight: 0.25
    popularity_weight: 0.05
    cold_content_weight: 0.9
    cold_popularity_weight: 0.1
    popularity_candidates: 10
evaluation: {{ks: [2, 3], split: test}}
""",
        encoding="utf-8",
    )
    config = load_config(config_path)
    config["data"]["source"] = source
    config["serving"] = {"enabled": True, "max_items": 100}
    if source == "sample_parquet":
        _sample_fixture(raw, tmp_path / "samples")
        config["paths"]["samples"] = str(tmp_path / "samples")
    spark = create_spark(config)
    try:
        manifest = prepare_dataset(spark, config)
        assert manifest["books"] == 6
        books_frame = spark.read.parquet(str(Path(config["paths"]["processed"]) / "books"))
        canonical = books_frame.filter("work_id = '101'").first()
        assert canonical["canonical_book_id"] == 1
        assert "to-read" not in canonical["shelves"]
        assert books_frame.filter("work_id = '102'").first()["canonical_book_id"] == 2
        if source == "sample_parquet":
            assert canonical["publication_year"] is None
            assert canonical["genres"] == ["fantasy, paranormal"]
            assert canonical["authors"] == ["Test Author"]
        mapping = spark.read.parquet(str(Path(config["paths"]["processed"]) / "edition_to_work"))
        mapped_editions = mapping.filter("edition_id IN (1, 7)").collect()
        assert {row["work_id"] for row in mapped_editions} == {"101"}
        assert len({row["item_idx"] for row in mapped_editions}) == 1

        interactions = spark.read.parquet(str(Path(config["paths"]["processed"]) / "interactions"))
        held_out = interactions.filter("split IN ('validation', 'test')").groupBy(
            "user_id", "split"
        )
        assert all(row["count"] == 1 for row in held_out.count().collect())

        run_id, run_dir = train_models(spark, config, ["all"], "integration")
        assert run_id == "integration"
        report = evaluate_run(spark, config, run_dir)
        assert "hybrid" in report["models"]
        rows = recommend(spark, config, run_dir, user_id=1, top_k=2)
        assert rows
        assert len({row["work_id"] for row in rows}) == len(rows)
        seen_works = {
            row["work_id"]
            for row in interactions.filter("user_id = 1 AND split = 'train'")
            .select("work_id")
            .collect()
        }
        assert all(row["work_id"] not in seen_works for row in rows)
        assert rows == recommend(spark, config, run_dir, user_id=1, top_k=2)
        cold_rows = recommend(spark, config, run_dir, seed_book_ids=[1], top_k=2)
        assert cold_rows
        assert all(row["canonical_book_id"] != 1 for row in cold_rows)
        assert recommend(spark, config, run_dir, user_id=9999, top_k=2)
        assert (run_dir / "metrics.json").exists()
        engine = DemoRecommender(run_dir / "serving")
        import httpx
        from fastapi.testclient import TestClient

        from books_recommender.serving.api import CatalogResolver, create_app

        def catalog(request):
            ids = json.loads(request.content)["ids"]
            return httpx.Response(200, json=[{"id": n, "goodreads_id": n - 2000} for n in ids])

        resolver = CatalogResolver(
            "http://catalog",
            httpx.Client(base_url="http://catalog", transport=httpx.MockTransport(catalog)),
        )
        app = create_app(run_dir / "serving", engine=engine, resolver=resolver)
        with TestClient(app) as client:
            response = client.post(
                "/recommend",
                json={
                    "userId": "app-user-uuid",
                    "preferences": {"favorite_books": ["2001"]},
                    "candidates": [str(n + 2000) for n in range(1, 8)],
                },
            )
        assert response.status_code == 200
        assert response.json()["books"]
        assert all(row["id"] not in {"2001", "2007"} for row in response.json()["books"])
    finally:
        spark.stop()
