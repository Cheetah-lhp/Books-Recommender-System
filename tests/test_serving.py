import json

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fastapi.testclient import TestClient

from books_recommender.serving.api import CatalogResolver, create_app
from books_recommender.serving.runtime import DemoRecommender


@pytest.fixture
def bundle(tmp_path):
    def write(name, rows):
        folder = tmp_path / name
        folder.mkdir()
        pq.write_table(pa.Table.from_pylist(rows), folder / "part.parquet")

    manifest = {
        "run_id": "test",
        "book_id_namespace": "book_id_csv",
        "num_features": 2,
        "max_history": 50,
        "als": {"rank": 2, "reg_param": 0.05, "alpha": 20},
        "hybrid": {
            "als_weight": 0.7,
            "content_weight": 0.25,
            "popularity_weight": 0.05,
            "cold_content_weight": 0.9,
            "cold_popularity_weight": 0.1,
        },
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    write(
        "items",
        [
            {
                "item_idx": i,
                "work_id": str(i),
                "canonical_book_id": i * 10,
                "title": f"Book {i}",
                "genres": ["fantasy, paranormal"] if i < 3 else ["history, biography"],
                "features": {"type": 0, "size": 2, "indices": [0 if i < 3 else 1], "values": [1.0]},
                "popularity": float(10 - i),
            }
            for i in range(1, 5)
        ],
    )
    write(
        "aliases",
        [{"source_book_id": str(i * 10), "item_idx": i} for i in range(1, 5)]
        + [{"source_book_id": "11", "item_idx": 1}],
    )
    write(
        "als_items",
        [{"id": i, "features": [1.0, 0.1] if i < 3 else [0.1, 1.0]} for i in range(1, 5)],
    )
    return tmp_path


ID_MAP = {"101": "10", "102": "11", "200": "20", "300": "30", "400": "40"}


def test_live_signals_rerank_only_supplied_candidates_and_exclude_work(bundle):
    engine = DemoRecommender(bundle)
    payload = {
        "userId": "uuid-a",
        "preferences": {"favorite_books": ["101"]},
        "history": [{"book_id": "300", "status": "read"}],
        "feedback": {"hidden": ["400"]},
        "candidates": ["101", "102", "200", "300", "400", "999"],
    }
    result = engine.rerank(payload, ID_MAP)
    assert [row["id"] for row in result["books"]] == ["200"]
    assert result["books"][0]["score"] > 0
    payload["userId"] = "uuid-b"
    assert engine.rerank(payload, ID_MAP) == result


def test_popularity_genres_and_low_ratings(bundle):
    engine = DemoRecommender(bundle)
    payload = {"candidates": ["200", "300", "400", "999"]}
    assert engine.rerank(payload, ID_MAP)["books"][0]["id"] == "200"
    payload["preferences"] = {"genres": ["History & Biography"]}
    assert engine.rerank(payload, ID_MAP)["books"][0]["id"] == "300"
    payload["ratings"] = [{"book_id": "300", "rating": 1}]
    assert engine.rerank(payload, ID_MAP)["books"][0]["id"] == "400"
    assert engine.rerank({"candidates": ["unknown"]}, ID_MAP)["books"] == []


def test_api_contract_and_catalog_id_lookup(bundle):
    calls = []

    def catalog(request):
        ids = json.loads(request.content)["ids"]
        calls.append(ids)
        return httpx.Response(
            200,
            json=[{"id": n, "goodreads_id": int(ID_MAP[str(n)])} for n in ids if str(n) in ID_MAP],
        )

    resolver = CatalogResolver(
        "http://catalog",
        httpx.Client(base_url="http://catalog", transport=httpx.MockTransport(catalog)),
    )
    app = create_app(bundle, api_key="secret", resolver=resolver)
    with TestClient(app) as client:
        assert client.get("/health").json()["run_id"] == "test"
        assert client.post("/recommend", json={}).status_code == 401
        headers = {"Authorization": "Bearer secret"}
        payload = {
            "userId": "5",
            "preferences": {"favorite_books": ["101"]},
            "candidates": ["102", "200", "300"],
        }
        response = client.post("/recommend", json=payload, headers=headers)
        assert response.status_code == 200
        ids = {row["id"] for row in response.json()["books"]}
        assert ids == {"200", "300"}
        assert resolver.resolve(["200", "102"]) == {"200": "20", "102": "11"}
        assert len(calls) == 1
        assert (
            client.post(
                "/recommend", json={"ratings": [{"book_id": "1", "rating": 9}]}, headers=headers
            ).status_code
            == 422
        )


def test_catalog_failure_returns_503_for_frontend_fallback(bundle):
    resolver = CatalogResolver(
        "http://catalog",
        httpx.Client(
            base_url="http://catalog", transport=httpx.MockTransport(lambda _: httpx.Response(500))
        ),
    )
    with TestClient(create_app(bundle, resolver=resolver)) as client:
        assert client.post("/recommend", json={"candidates": ["200"]}).status_code == 503
