from typing import Optional, List, Dict, Any, Tuple

def _prepare_sql(sql: str, db_type: str) -> str:
    # Chuyen doi placeholder %s sang ? cho SQLite
    return sql.replace("%s", "?") if db_type == "sqlite" else sql

def get_total_count(conn, db_type: str) -> int:
    # Dem tong so sach trong CSDL
    with conn.cursor() as cur:
        sql = "SELECT COUNT(*) AS total FROM books;"
        cur.execute(sql)
        res = cur.fetchone()
        return res["total"] if isinstance(res, dict) else res[0]

def get_books_paginated(
    conn,
    db_type: str,
    limit: int,
    offset: int,
    q: Optional[str] = None,
    category: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
    sort: str = "rating",
) -> Tuple[int, List[Dict[str, Any]]]:
    # Truy van danh sach sach co loc va phan trang
    params = []
    where_clauses = []

    if q:
        where_clauses.append("(title LIKE %s OR author_name LIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if category:
        category_matches = []
        for term in category:
            normalized_term = term.strip().lower().replace(" ", "%").replace("-", "%")
            if normalized_term:
                category_matches.append("LOWER(category) LIKE %s")
                params.append(f"%{normalized_term}%")
        if category_matches:
            where_clauses.append(
                "goodreads_id IN (SELECT book_id FROM book_categories WHERE "
                + " OR ".join(category_matches)
                + ")"
            )

    if min_rating is not None:
        where_clauses.append("rating >= %s")
        params.append(min_rating)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sort_map = {
        "rating": "rating DESC, ratings_count DESC",
        "ratings_count": "ratings_count DESC",
        "trending": "trending_rank IS NULL, trending_rank ASC, rating DESC",
        "title": "title ASC",
        "published_year": "published_year IS NULL, published_year DESC",
    }
    order_sql = sort_map.get(sort, "rating DESC")

    with conn.cursor() as cur:
        count_sql = _prepare_sql(f"SELECT COUNT(*) AS total FROM books {where_sql}", db_type)
        cur.execute(count_sql, params)
        res = cur.fetchone()
        total = res["total"] if isinstance(res, dict) else res[0]

        query_sql = _prepare_sql(
            f"""
            SELECT id, goodreads_id, title, author_name, description, cover_url,
                   isbn, isbn13, published_year, pages, language, rating,
                   ratings_count, publisher, tags, trending_rank, price
            FROM books {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            db_type,
        )
        all_params = params + [limit, offset]
        cur.execute(query_sql, all_params)
        rows = cur.fetchall()

    return total, rows

def get_trending_books(conn, db_type: str, limit: int) -> List[Dict[str, Any]]:
    # Lay danh sach sach trending
    with conn.cursor() as cur:
        sql = _prepare_sql(
            """
            SELECT id, goodreads_id, title, author_name, description, cover_url,
                   isbn, isbn13, published_year, pages, language, rating,
                   ratings_count, publisher, tags, trending_rank, price
            FROM books
            ORDER BY trending_rank IS NULL, trending_rank ASC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [limit])
        return cur.fetchall()

def get_top_rated_books(conn, db_type: str, limit: int) -> List[Dict[str, Any]]:
    # Lay danh sach sach co danh gia cao
    with conn.cursor() as cur:
        sql = _prepare_sql(
            """
            SELECT id, goodreads_id, title, author_name, description, cover_url,
                   isbn, isbn13, published_year, pages, language, rating,
                   ratings_count, publisher, tags, trending_rank, price
            FROM books
            WHERE ratings_count >= 50
            ORDER BY rating DESC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [limit])
        return cur.fetchall()

def search_books(conn, db_type: str, q: str, limit: int) -> List[Dict[str, Any]]:
    # Tim kiem sach theo ten hoac tac gia
    with conn.cursor() as cur:
        sql = _prepare_sql(
            """
            SELECT id, goodreads_id, title, author_name, description, cover_url,
                   isbn, isbn13, published_year, pages, language, rating,
                   ratings_count, publisher, tags, trending_rank, price
            FROM books
            WHERE title LIKE %s OR author_name LIKE %s
            ORDER BY rating DESC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [f"%{q}%", f"%{q}%", limit])
        return cur.fetchall()

def get_books_batch(conn, db_type: str, ids: List[int]) -> List[Dict[str, Any]]:
    # Lay danh sach sach theo danh sach ID
    if not ids:
        return []
    placeholders = ", ".join(["%s"] * len(ids))
    sql = _prepare_sql(
        f"""
        SELECT id, goodreads_id, title, author_name, description, cover_url,
               isbn, isbn13, published_year, pages, language, rating,
               ratings_count, publisher, tags, trending_rank, price
        FROM books WHERE id IN ({placeholders})
        """,
        db_type,
    )
    with conn.cursor() as cur:
        cur.execute(sql, ids)
        return cur.fetchall()

def get_book_by_id(conn, db_type: str, book_id: int) -> Optional[Dict[str, Any]]:
    # Lay thong tin chi tiet mot cuon sach
    sql = _prepare_sql(
        """
        SELECT id, goodreads_id, title, author_name, description, cover_url,
               isbn, isbn13, published_year, pages, language, rating,
               ratings_count, publisher, tags, trending_rank, price
        FROM books
        WHERE id = %s OR goodreads_id = %s
        ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END
        LIMIT 1
        """,
        db_type,
    )
    with conn.cursor() as cur:
        cur.execute(sql, [book_id, book_id, book_id])
        return cur.fetchone()

def get_target_book_categories(conn, db_type: str, goodreads_id: int) -> List[str]:
    # Lay the loai cua cuon sach muc tieu
    sql = _prepare_sql("SELECT category FROM book_categories WHERE book_id = %s", db_type)
    with conn.cursor() as cur:
        cur.execute(sql, [goodreads_id])
        return [row["category"] for row in cur.fetchall()]

def get_similar_books(
    conn,
    db_type: str,
    target_id: int,
    author_name: str,
    language: str,
    book_tag_terms: List[str],
    preferred_tag_terms: List[str],
    normalized_tags: List[str],
    limit: int,
) -> List[Dict[str, Any]]:
    # Tim cac cuon sach tuong dong theo the loai hoac tac gia
    with conn.cursor() as cur:
        if normalized_tags:
            placeholders = ", ".join(["%s"] * len(normalized_tags))
            score_parts = []
            score_params = []
            if book_tag_terms:
                b_placeholders = ", ".join(["%s"] * len(book_tag_terms))
                score_parts.append(
                    f"2 * (SELECT COUNT(DISTINCT c.category) FROM book_categories c "
                    f"WHERE c.book_id = b.goodreads_id "
                    f"AND LOWER(REPLACE(c.category, ' ', '-')) IN ({b_placeholders}))"
                )
                score_params.extend(book_tag_terms)
            if preferred_tag_terms:
                p_placeholders = ", ".join(["%s"] * len(preferred_tag_terms))
                score_parts.append(
                    f"(SELECT COUNT(DISTINCT c.category) FROM book_categories c "
                    f"WHERE c.book_id = b.goodreads_id "
                    f"AND LOWER(REPLACE(c.category, ' ', '-')) IN ({p_placeholders}))"
                )
                score_params.extend(preferred_tag_terms)
            match_score = " + ".join(score_parts) or "0"
            sql = f"""
                SELECT b.id, b.goodreads_id, b.title, b.author_name, b.description,
                       b.cover_url, b.isbn, b.isbn13, b.published_year, b.pages,
                       b.language, b.rating, b.ratings_count, b.publisher, b.tags,
                       b.trending_rank, b.price,
                       ({match_score}) AS matched_tag_score
                FROM books b
                WHERE b.id <> %s
                  AND EXISTS (
                      SELECT 1 FROM book_categories c
                      WHERE c.book_id = b.goodreads_id
                        AND LOWER(REPLACE(c.category, ' ', '-')) IN ({placeholders})
                  )
                ORDER BY matched_tag_score DESC, b.rating DESC, b.ratings_count DESC
                LIMIT %s
            """
            cur.execute(_prepare_sql(sql, db_type), [*score_params, target_id, *normalized_tags, limit])
        else:
            sql = """
                SELECT id, goodreads_id, title, author_name, description, cover_url,
                       isbn, isbn13, published_year, pages, language, rating,
                       ratings_count, publisher, tags, trending_rank, price
                FROM books
                WHERE id <> %s AND (author_name = %s OR language = %s)
                ORDER BY CASE WHEN author_name = %s THEN 0 ELSE 1 END,
                         rating DESC, ratings_count DESC
                LIMIT %s
            """
            cur.execute(_prepare_sql(sql, db_type), [target_id, author_name, language, author_name, limit])
        return cur.fetchall()

def get_sample_reviews(conn, db_type: str, goodreads_id: int, limit: int) -> List[Dict[str, Any]]:
    # Lay cac review mau cho cuon sach
    sql = _prepare_sql(
        """
        SELECT review_id, user_id, rating, review_text, date_added
        FROM sample_reviews
        WHERE book_id = %s
        ORDER BY date_added DESC
        LIMIT %s
        """,
        db_type,
    )
    with conn.cursor() as cur:
        cur.execute(sql, [goodreads_id, limit])
        return cur.fetchall()

def get_categories_summary(conn, db_type: str, limit: int = 50) -> List[Dict[str, Any]]:
    # Lay thong ke top the loai
    sql = _prepare_sql(
        """
        SELECT category, COUNT(*) AS count
        FROM book_categories
        GROUP BY category
        ORDER BY count DESC
        LIMIT %s;
        """,
        db_type,
    )
    with conn.cursor() as cur:
        cur.execute(sql, [limit])
        return cur.fetchall()

def get_database_stats(conn, db_type: str) -> Dict[str, Any]:
    # Lay thong ke tong quat ve CSDL
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM books;")
        r1 = cur.fetchone()
        total = r1["total"] if isinstance(r1, dict) else r1[0]

        cur.execute("SELECT COUNT(*) AS total FROM book_categories;")
        r2 = cur.fetchone()
        cat_total = r2["total"] if isinstance(r2, dict) else r2[0]

        cur.execute("SELECT AVG(rating) AS avg_rating FROM books WHERE ratings_count > 0;")
        r3 = cur.fetchone()
        avg_rating = r3["avg_rating"] if isinstance(r3, dict) else r3[0]

    return {
        "total_books": total,
        "total_category_tags": cat_total,
        "avg_rating": round(float(avg_rating or 0), 2),
    }

