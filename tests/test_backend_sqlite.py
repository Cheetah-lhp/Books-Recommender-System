import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pymysql")


def test_sqlite_catalog_supports_context_managed_cursors(tmp_path, monkeypatch):
    from web.backend import init_sample_data, main

    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setattr(main, "SQLITE_PATH", tmp_path / "catalog.db")
    _, connection = main.get_conn()
    init_sample_data.init_schema("sqlite", connection)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO books (goodreads_id,title,author_name,rating,ratings_count,tags) "
            "VALUES (9001,'Demo book','Author',4.5,25,'[\"fantasy\"]')"
        )
    connection.commit()
    connection.close()
    with TestClient(main.app) as client:
        response = client.get("/api/books?limit=100&sort=ratings_count")
        assert response.status_code == 200
        book = response.json()["data"][0]
        assert book["id"] == 1
        assert book["goodreads_id"] == 9001
        assert book["tags"] == ["fantasy"]
        response = client.post("/api/books/batch", json={"ids": [1]})
        assert response.status_code == 200
        assert response.json()[0]["goodreads_id"] == 9001


def test_refresh_covers_preserves_database_ids_and_other_book_fields(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    from web.backend import init_sample_data, main

    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setattr(main, "SQLITE_PATH", tmp_path / "catalog.db")
    _, connection = main.get_conn()
    init_sample_data.init_schema("sqlite", connection)
    connection.execute(
        "INSERT INTO books (id,goodreads_id,title,author_name,cover_url,rating) "
        "VALUES (1,9001,'Keep title','Author','https://example.com/old.jpg',4.5)"
    )
    connection.commit()
    source = tmp_path / "samples" / "books"
    source.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"book_id": 9001, "image_url": "https://example.com/new.jpg"},
                {"book_id": 9002, "image_url": "https://example.com/unused.jpg"},
            ]
        ),
        source / "part.parquet",
    )

    assert init_sample_data.refresh_sample_covers("sqlite", connection, source.parent) == 1
    row = connection.execute("SELECT * FROM books").fetchone()
    assert (row["id"], row["goodreads_id"], row["title"], row["rating"]) == (
        1,
        9001,
        "Keep title",
        4.5,
    )
    assert row["cover_url"] == "https://example.com/new.jpg"
    assert connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 1
    assert init_sample_data.refresh_sample_covers("sqlite", connection, source.parent) == 0
    connection.close()
