from app.services.recommender import Signals, score_book


def test_score_book_prefers_matching_genre():
    catalog = [
        {
            "id": "1",
            "title": "Fantasy Epic",
            "author_name": "A",
            "rating": 4.0,
            "ratings_count": 100,
            "tags": ["fantasy", "magic"],
            "categories": ["fantasy"],
            "pages": 400,
            "trending_rank": None,
        },
        {
            "id": "2",
            "title": "Cookbook",
            "author_name": "B",
            "rating": 4.8,
            "ratings_count": 100,
            "tags": ["cooking"],
            "categories": ["food"],
            "pages": 200,
            "trending_rank": None,
        },
    ]
    signals = Signals(genres=["Fantasy"])
    s1, _ = score_book(catalog[0], signals, catalog)
    s2, _ = score_book(catalog[1], signals, catalog)
    assert s1 > s2
