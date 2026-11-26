from contextlib import contextmanager
from datetime import date, datetime
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


@contextmanager
def _cursor(conn):
    cur = conn.cursor()
    try:
        yield cur
    finally:
        if hasattr(cur, "close"):
            cur.close()


_SCHEMA_CACHE_LOCK = threading.Lock()
_FULL_SCHEMA_CACHE: Dict[Tuple[str, str, str], bool] = {}
_DISTINCT_GENRES_CACHE: Dict[Tuple[str, str, str], List[str]] = {}
_TTL_CACHE_LOCK = threading.Lock()
_CATEGORIES_SUMMARY_CACHE: Dict[Tuple[str, str, str], Tuple[float, List[Dict[str, Any]]]] = {}
_GENRE_FILTER_COUNT_CACHE: Dict[Tuple[str, str, str, Tuple[str, ...]], Tuple[float, int]] = {}
_TOTAL_COUNT_CACHE: Dict[Tuple[str, str, str], Tuple[float, int]] = {}
_STATS_CACHE: Dict[Tuple[str, str, str], Tuple[float, Dict[str, Any]]] = {}
_MYSQL_CATALOG_CACHE_TTL = 600.0

_EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that",
    "the", "their", "then", "there", "these", "they", "this", "to", "was",
    "will", "with",
}

_FULL_BOOK_SELECT = """
    SELECT
        b.book_id AS id,
        b.book_id AS goodreads_id,
        b.title AS title,
        NULL AS author_name,
        b.description AS description,
        b.image_url AS cover_url,
        b.isbn AS isbn,
        b.isbn13 AS isbn13,
        b.publication_year AS published_year,
        b.num_pages AS pages,
        b.language_code AS language,
        b.average_rating AS rating,
        b.ratings_count AS ratings_count,
        b.publisher AS publisher,
        NULL AS tags,
        NULL AS trending_rank,
        NULL AS price
    FROM books b
"""

_LEGACY_BOOK_COLUMNS = """
    id, goodreads_id, title, author_name, description, cover_url,
    isbn, isbn13, published_year, pages, language, rating,
    ratings_count, publisher, tags, trending_rank, price
"""


def _prepare_sql(sql: str, db_type: str) -> str:
    """Chuyen %s thanh ? khi su dung SQLite."""
    if db_type == "sqlite":
        return sql.replace("%s", "?")
    return sql


def _conn_cache_key(conn, db_type: str) -> Optional[Tuple[str, str, str]]:
    if db_type != "mysql":
        return None
    host = str(getattr(conn, "host", "") or "")
    db = str(getattr(conn, "db", b"") or "")
    return (db_type, host, db)


def _row_val(row: Any, key: str, idx: int = 0) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except Exception:
        return row[idx]


def _normalize_row(row: Any) -> Dict[str, Any]:
    return dict(row) if not isinstance(row, dict) else dict(row)


def _is_full_schema(conn, db_type: str) -> bool:
    """Phat hien schema Goodreads day du (books co cot book_id thay vi goodreads_id)."""
    key = _conn_cache_key(conn, db_type)
    if key is not None:
        with _SCHEMA_CACHE_LOCK:
            cached = _FULL_SCHEMA_CACHE.get(key)
        if cached is not None:
            return cached

    is_full = False
    with _cursor(conn) as cur:
        if db_type == "mysql":
            cur.execute("SHOW COLUMNS FROM `books` LIKE 'book_id'")
            is_full = cur.fetchone() is not None
        else:
            cur.execute("PRAGMA table_info(books)")
            cols = {_row_val(r, "name", 1) for r in cur.fetchall()}
            is_full = "book_id" in cols

    if key is not None:
        with _SCHEMA_CACHE_LOCK:
            _FULL_SCHEMA_CACHE[key] = is_full
    return is_full


def _get_distinct_genres(conn, db_type: str) -> List[str]:
    key = _conn_cache_key(conn, db_type)
    if key is not None:
        with _SCHEMA_CACHE_LOCK:
            cached = _DISTINCT_GENRES_CACHE.get(key)
        if cached is not None:
            return cached

    with _cursor(conn) as cur:
        cur.execute("SELECT DISTINCT genres FROM genres")
        genres = [
            str(_row_val(r, "genres", 0))
            for r in cur.fetchall()
            if _row_val(r, "genres", 0)
        ]

    if key is not None and genres:
        with _SCHEMA_CACHE_LOCK:
            _DISTINCT_GENRES_CACHE[key] = genres
    return genres


def _normalize_slug(text: str) -> str:
    return re.sub(r"[\s,_-]+", " ", (text or "").strip().lower()).strip()


def _match_genre_labels(terms: List[str], available_genres: List[str]) -> List[str]:
    """Anh xa slug/ten the loai tu frontend sang gia tri chinh xac trong bang genres."""
    matched: List[str] = []
    seen = set()
    for term in terms:
        norm_term = _normalize_slug(term)
        if not norm_term:
            continue
        term_tokens = set(norm_term.split())
        for g in available_genres:
            if g in seen:
                continue
            norm_g = _normalize_slug(g)
            g_parts = [_normalize_slug(p) for p in g.split(",")]
            if (
                norm_term == norm_g
                or norm_term in g_parts
                or norm_term in norm_g
                or term_tokens.issubset(set(norm_g.split()))
            ):
                seen.add(g)
                matched.append(g)
    return matched


def _ft_boolean_query(q: str) -> str:
    """Tao chuoi tim kiem MySQL FULLTEXT BOOLEAN MODE tu cac tu khoa hop le."""
    words = re.findall(r"[0-9A-Za-z_]+", (q or "").strip())
    tokens = [w for w in words if len(w) >= 3 and w.lower() not in _EN_STOPWORDS]
    if not tokens:
        return ""
    return " ".join(f"+{w}*" if len(w) >= 4 else f"+{w}" for w in tokens[:6])


def _find_book_ids_by_author_query(cur, db_type: str, q: str, limit_authors: int = 80, limit_books: int = 800) -> List[int]:
    if not q or not q.strip():
        return []
    author_ids: List[str] = []
    if db_type == "mysql":
        ft_q = _ft_boolean_query(q)
        if ft_q:
            cur.execute(
                "SELECT author_id FROM authors WHERE MATCH(name) AGAINST(%s IN BOOLEAN MODE) LIMIT %s",
                [ft_q, limit_authors],
            )
            author_ids = [str(_row_val(r, "author_id", 0)) for r in cur.fetchall() if _row_val(r, "author_id", 0)]
        if not author_ids:
            cur.execute(
                "SELECT author_id FROM authors WHERE name LIKE %s LIMIT %s",
                [f"{q.strip()}%", limit_authors],
            )
            author_ids = [str(_row_val(r, "author_id", 0)) for r in cur.fetchall() if _row_val(r, "author_id", 0)]
    else:
        cur.execute(
            "SELECT author_id FROM authors WHERE LOWER(name) LIKE LOWER(?) LIMIT ?",
            [f"%{q.strip()}%", limit_authors],
        )
        author_ids = [str(_row_val(r, "author_id", 0)) for r in cur.fetchall() if _row_val(r, "author_id", 0)]

    if not author_ids:
        return []
    ph = ", ".join(["%s"] * len(author_ids))
    sql = _prepare_sql(
        f"SELECT DISTINCT book_id FROM book_authors_map WHERE author_id IN ({ph}) LIMIT %s",
        db_type,
    )
    cur.execute(sql, [*author_ids, limit_books])
    return [int(_row_val(r, "book_id", 0)) for r in cur.fetchall() if _row_val(r, "book_id", 0) is not None]


def _find_book_ids_by_exact_author(cur, db_type: str, author_name: str, limit_books: int = 1000) -> List[int]:
    name = (author_name or "").strip()
    if not name:
        return []
    if db_type == "mysql":
        cur.execute(
            "SELECT author_id FROM authors WHERE name = %s OR name LIKE %s LIMIT 50",
            [name, f"{name},%"],
        )
    else:
        cur.execute(
            "SELECT author_id FROM authors WHERE LOWER(TRIM(name)) = LOWER(?) LIMIT 50",
            [name],
        )
    author_ids = [str(_row_val(r, "author_id", 0)) for r in cur.fetchall() if _row_val(r, "author_id", 0)]
    if not author_ids:
        return []
    ph = ", ".join(["%s"] * len(author_ids))
    sql = _prepare_sql(
        f"SELECT DISTINCT book_id FROM book_authors_map WHERE author_id IN ({ph}) LIMIT %s",
        db_type,
    )
    cur.execute(sql, [*author_ids, limit_books])
    return [int(_row_val(r, "book_id", 0)) for r in cur.fetchall() if _row_val(r, "book_id", 0) is not None]


def _hydrate_full_books(cur, db_type: str, rows: List[Any]) -> List[Dict[str, Any]]:
    """Bo sung author_name va tags cho danh sach sach da truy van tu schema Goodreads."""
    normalized = [_normalize_row(r) for r in rows]
    book_ids = [r["id"] for r in normalized if r.get("id") is not None]
    if not book_ids:
        return normalized

    ph = ", ".join(["%s"] * len(book_ids))
    bam_sql = _prepare_sql(
        f"SELECT book_id, author_id, role FROM book_authors_map WHERE book_id IN ({ph})",
        db_type,
    )
    cur.execute(bam_sql, book_ids)
    bam_rows = cur.fetchall()

    author_ids: List[str] = []
    seen_aids = set()
    book_to_authors: Dict[int, List[Tuple[int, str]]] = {}
    for r in bam_rows:
        bid = _row_val(r, "book_id", 0)
        aid = _row_val(r, "author_id", 1)
        role = (_row_val(r, "role", 2) or "").strip()
        if bid is None or not aid:
            continue
        aid_str = str(aid)
        priority = 0 if role == "" else 1
        book_to_authors.setdefault(int(bid), []).append((priority, aid_str))
        if aid_str not in seen_aids:
            seen_aids.add(aid_str)
            author_ids.append(aid_str)

    author_names: Dict[str, str] = {}
    if author_ids:
        a_ph = ", ".join(["%s"] * len(author_ids))
        a_sql = _prepare_sql(
            f"SELECT author_id, name FROM authors WHERE author_id IN ({a_ph})",
            db_type,
        )
        cur.execute(a_sql, author_ids)
        for ar in cur.fetchall():
            aid_val = _row_val(ar, "author_id", 0)
            name_val = _row_val(ar, "name", 1)
            if aid_val and name_val:
                author_names[str(aid_val)] = str(name_val)

    genre_sql = _prepare_sql(
        f"SELECT book_id, genres, votes FROM genres WHERE book_id IN ({ph}) ORDER BY votes DESC",
        db_type,
    )
    cur.execute(genre_sql, book_ids)
    book_genres_pos: Dict[int, List[str]] = {}
    book_genres_all: Dict[int, List[str]] = {}
    for gr in cur.fetchall():
        bid = _row_val(gr, "book_id", 0)
        gname = _row_val(gr, "genres", 1)
        votes = _row_val(gr, "votes", 2)
        if bid is None or not gname:
            continue
        bid_int = int(bid)
        g_str = str(gname)
        all_list = book_genres_all.setdefault(bid_int, [])
        if g_str not in all_list:
            all_list.append(g_str)
        if votes is None or int(votes) > 0:
            pos_list = book_genres_pos.setdefault(bid_int, [])
            if g_str not in pos_list:
                pos_list.append(g_str)

    for b in normalized:
        bid = b.get("id")
        if bid is None:
            continue
        bid_int = int(bid)
        links = sorted(book_to_authors.get(bid_int, []), key=lambda x: x[0])
        names: List[str] = []
        for _, aid in links:
            nm = author_names.get(aid)
            if nm and nm not in names:
                names.append(nm)
        b["author_name"] = ", ".join(names) if names else "Unknown Author"
        tags = book_genres_pos.get(bid_int) or book_genres_all.get(bid_int) or []
        b["tags"] = tags
    return normalized


def get_total_count(conn, db_type: str) -> int:
    # Dem tong so sach trong database
    key = _conn_cache_key(conn, db_type)
    if key is not None:
        with _TTL_CACHE_LOCK:
            hit = _TOTAL_COUNT_CACHE.get(key)
        if hit and (time.monotonic() - hit[0] < _MYSQL_CATALOG_CACHE_TTL):
            return hit[1]

    with _cursor(conn) as cur:
        cur.execute("SELECT COUNT(*) AS total FROM books;")
        res = cur.fetchone()
        total = int(res["total"] if isinstance(res, dict) else res[0])

    if key is not None:
        with _TTL_CACHE_LOCK:
            _TOTAL_COUNT_CACHE[key] = (time.monotonic(), total)
    return total


def get_books_paginated(
    conn,
    db_type: str,
    limit: int,
    offset: int,
    q: Optional[str] = None,
    category: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
    sort: str = "rating",
    author: Optional[str] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    if _is_full_schema(conn, db_type):
        return _get_books_paginated_full(
            conn, db_type, limit, offset, q=q, category=category,
            min_rating=min_rating, sort=sort, author=author,
        )

    # Truy van danh sach sach co loc va phan trang (schema legacy)
    params: List[Any] = []
    where_clauses: List[str] = []

    if q:
        where_clauses.append("(title LIKE %s OR author_name LIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if author:
        name = author.strip()
        if name:
            where_clauses.append(
                "("
                "LOWER(TRIM(author_name)) = LOWER(%s) "
                "OR LOWER(author_name) LIKE LOWER(%s) "
                "OR LOWER(author_name) LIKE LOWER(%s) "
                "OR LOWER(author_name) LIKE LOWER(%s)"
                ")"
            )
            params.extend([name, f"{name},%", f"%, {name}", f"%, {name},%"])

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

    with _cursor(conn) as cur:
        count_sql = _prepare_sql(f"SELECT COUNT(*) AS total FROM books {where_sql}", db_type)
        cur.execute(count_sql, params)
        res = cur.fetchone()
        total = int(res["total"] if isinstance(res, dict) else res[0])

        query_sql = _prepare_sql(
            f"""
            SELECT {_LEGACY_BOOK_COLUMNS}
            FROM books {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            db_type,
        )
        cur.execute(query_sql, [*params, limit, offset])
        rows = [_normalize_row(r) for r in cur.fetchall()]

    return total, rows


def _get_books_paginated_full(
    conn,
    db_type: str,
    limit: int,
    offset: int,
    q: Optional[str] = None,
    category: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
    sort: str = "rating",
    author: Optional[str] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    params: List[Any] = []
    where_clauses: List[str] = []

    with _cursor(conn) as cur:
        if q:
            q_clean = q.strip()
            author_book_ids = _find_book_ids_by_author_query(cur, db_type, q_clean)
            title_clause = ""
            title_params: List[Any] = []
            if db_type == "mysql":
                ft_q = _ft_boolean_query(q_clean)
                if ft_q:
                    title_clause = "MATCH(b.title) AGAINST(%s IN BOOLEAN MODE)"
                    title_params.append(ft_q)
                else:
                    title_clause = "b.title LIKE %s"
                    title_params.append(f"%{q_clean}%")
            else:
                title_clause = "LOWER(b.title) LIKE LOWER(%s)"
                title_params.append(f"%{q_clean}%")

            if author_book_ids:
                a_ph = ", ".join(["%s"] * len(author_book_ids))
                where_clauses.append(f"({title_clause} OR b.book_id IN ({a_ph}))")
                params.extend(title_params)
                params.extend(author_book_ids)
            else:
                where_clauses.append(title_clause)
                params.extend(title_params)

        if author and author.strip():
            exact_book_ids = _find_book_ids_by_exact_author(cur, db_type, author)
            if not exact_book_ids:
                return 0, []
            e_ph = ", ".join(["%s"] * len(exact_book_ids))
            where_clauses.append(f"b.book_id IN ({e_ph})")
            params.extend(exact_book_ids)

        if category:
            available_genres = _get_distinct_genres(conn, db_type)
            matched_genres = _match_genre_labels(category, available_genres)
            if not matched_genres:
                return 0, []
            g_ph = ", ".join(["%s"] * len(matched_genres))
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM genres g WHERE g.book_id = b.book_id "
                f"AND g.genres IN ({g_ph}) AND g.votes > 0)"
            )
            params.extend(matched_genres)

        if min_rating is not None:
            where_clauses.append("b.average_rating >= %s")
            params.append(min_rating)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        sort_map = {
            "rating": ("b.average_rating DESC, b.ratings_count DESC", "idx_books_avg_ratings"),
            "ratings_count": ("b.ratings_count DESC, b.average_rating DESC", "idx_books_ratings_avg"),
            "trending": ("b.ratings_count DESC, b.average_rating DESC", "idx_books_ratings_avg"),
            "title": ("b.title ASC", ""),
            "published_year": ("b.publication_year DESC, b.ratings_count DESC", "idx_books_pub_year"),
        }
        order_sql, preferred_idx = sort_map.get(sort, ("b.average_rating DESC, b.ratings_count DESC", "idx_books_avg_ratings"))

        key = _conn_cache_key(conn, db_type)
        only_category = bool(category and not q and not (author and author.strip()) and min_rating is None)
        no_filters = not where_clauses

        if no_filters and key is not None:
            total = get_total_count(conn, db_type)
        elif only_category and key is not None:
            g_tuple = tuple(sorted(matched_genres))
            g_cache_key = (*key, g_tuple)
            with _TTL_CACHE_LOCK:
                hit = _GENRE_FILTER_COUNT_CACHE.get(g_cache_key)
            if hit and (time.monotonic() - hit[0] < _MYSQL_CATALOG_CACHE_TTL):
                total = hit[1]
            elif len(matched_genres) == 1:
                summary_rows = get_categories_summary(conn, db_type, limit=50)
                counts_map = {str(r["category"]): int(r["count"]) for r in summary_rows}
                total = counts_map.get(matched_genres[0], 0)
                with _TTL_CACHE_LOCK:
                    _GENRE_FILTER_COUNT_CACHE[g_cache_key] = (time.monotonic(), total)
            else:
                count_sql = _prepare_sql(f"SELECT COUNT(*) AS total FROM books b {where_sql}", db_type)
                cur.execute(count_sql, params)
                res = cur.fetchone()
                total = int(res["total"] if isinstance(res, dict) else res[0])
                with _TTL_CACHE_LOCK:
                    _GENRE_FILTER_COUNT_CACHE[g_cache_key] = (time.monotonic(), total)
        else:
            count_sql = _prepare_sql(f"SELECT COUNT(*) AS total FROM books b {where_sql}", db_type)
            cur.execute(count_sql, params)
            res = cur.fetchone()
            total = int(res["total"] if isinstance(res, dict) else res[0])

        use_force_idx = (
            db_type == "mysql"
            and preferred_idx
            and not q
            and not (author and author.strip())
        )
        from_clause = f"FROM books b FORCE INDEX ({preferred_idx})" if use_force_idx else "FROM books b"
        select_head = _FULL_BOOK_SELECT.replace("FROM books b", from_clause)

        query_sql = _prepare_sql(
            f"""
            {select_head}
            {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            db_type,
        )
        cur.execute(query_sql, [*params, limit, offset])
        rows = _hydrate_full_books(cur, db_type, cur.fetchall())

    return total, rows


def get_trending_books(conn, db_type: str, limit: int) -> List[Dict[str, Any]]:
    # Lay danh sach sach trending
    is_full = _is_full_schema(conn, db_type)
    with _cursor(conn) as cur:
        if is_full:
            sql = _prepare_sql(
                f"""
                {_FULL_BOOK_SELECT}
                ORDER BY b.ratings_count DESC, b.average_rating DESC
                LIMIT %s
                """,
                db_type,
            )
            cur.execute(sql, [limit])
            return _hydrate_full_books(cur, db_type, cur.fetchall())

        sql = _prepare_sql(
            f"""
            SELECT {_LEGACY_BOOK_COLUMNS}
            FROM books
            ORDER BY trending_rank IS NULL, trending_rank ASC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [limit])
        return [_normalize_row(r) for r in cur.fetchall()]


def get_top_rated_books(conn, db_type: str, limit: int) -> List[Dict[str, Any]]:
    # Lay danh sach sach co danh gia cao
    is_full = _is_full_schema(conn, db_type)
    with _cursor(conn) as cur:
        if is_full:
            sql = _prepare_sql(
                f"""
                {_FULL_BOOK_SELECT}
                WHERE b.ratings_count >= 50
                ORDER BY b.average_rating DESC, b.ratings_count DESC
                LIMIT %s
                """,
                db_type,
            )
            cur.execute(sql, [limit])
            return _hydrate_full_books(cur, db_type, cur.fetchall())

        sql = _prepare_sql(
            f"""
            SELECT {_LEGACY_BOOK_COLUMNS}
            FROM books
            WHERE ratings_count >= 50
            ORDER BY rating DESC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [limit])
        return [_normalize_row(r) for r in cur.fetchall()]


def search_books(conn, db_type: str, q: str, limit: int) -> List[Dict[str, Any]]:
    # Tim kiem sach theo ten hoac tac gia
    if _is_full_schema(conn, db_type):
        _, rows = _get_books_paginated_full(
            conn, db_type, limit=limit, offset=0, q=q, sort="ratings_count"
        )
        return rows

    with _cursor(conn) as cur:
        sql = _prepare_sql(
            f"""
            SELECT {_LEGACY_BOOK_COLUMNS}
            FROM books
            WHERE title LIKE %s OR author_name LIKE %s
            ORDER BY rating DESC, ratings_count DESC
            LIMIT %s
            """,
            db_type,
        )
        cur.execute(sql, [f"%{q}%", f"%{q}%", limit])
        return [_normalize_row(r) for r in cur.fetchall()]


def get_books_batch(conn, db_type: str, ids: List[int]) -> List[Dict[str, Any]]:
    # Lay danh sach sach theo danh sach ID
    if not ids:
        return []
    is_full = _is_full_schema(conn, db_type)
    placeholders = ", ".join(["%s"] * len(ids))
    with _cursor(conn) as cur:
        if is_full:
            sql = _prepare_sql(
                f"{_FULL_BOOK_SELECT} WHERE b.book_id IN ({placeholders})",
                db_type,
            )
            cur.execute(sql, ids)
            return _hydrate_full_books(cur, db_type, cur.fetchall())

        sql = _prepare_sql(
            f"SELECT {_LEGACY_BOOK_COLUMNS} FROM books WHERE id IN ({placeholders})",
            db_type,
        )
        cur.execute(sql, ids)
        return [_normalize_row(r) for r in cur.fetchall()]


def get_books_by_goodreads_ids(conn, db_type: str, goodreads_ids: List[int]) -> List[Dict[str, Any]]:
    """Hydrate catalog rows for hybrid-model edition IDs (book_id_csv / goodreads_id)."""
    if not goodreads_ids:
        return []
    if _is_full_schema(conn, db_type):
        return get_books_batch(conn, db_type, goodreads_ids)

    placeholders = ", ".join(["%s"] * len(goodreads_ids))
    sql = _prepare_sql(
        f"SELECT {_LEGACY_BOOK_COLUMNS} FROM books WHERE goodreads_id IN ({placeholders})",
        db_type,
    )
    with _cursor(conn) as cur:
        cur.execute(sql, goodreads_ids)
        return [_normalize_row(r) for r in cur.fetchall()]


def get_book_by_id(conn, db_type: str, book_id: int) -> Optional[Dict[str, Any]]:
    # Lay thong tin chi tiet mot cuon sach
    is_full = _is_full_schema(conn, db_type)
    with _cursor(conn) as cur:
        if is_full:
            sql = _prepare_sql(
                f"{_FULL_BOOK_SELECT} WHERE b.book_id = %s LIMIT 1",
                db_type,
            )
            cur.execute(sql, [book_id])
            row = cur.fetchone()
            if not row:
                return None
            return _hydrate_full_books(cur, db_type, [row])[0]

        sql = _prepare_sql(
            f"""
            SELECT {_LEGACY_BOOK_COLUMNS}
            FROM books
            WHERE id = %s OR goodreads_id = %s
            ORDER BY CASE WHEN id = %s THEN 0 ELSE 1 END
            LIMIT 1
            """,
            db_type,
        )
        cur.execute(sql, [book_id, book_id, book_id])
        row = cur.fetchone()
        return _normalize_row(row) if row else None


def get_target_book_categories(conn, db_type: str, goodreads_id: int) -> List[str]:
    # Lay the loai cua cuon sach muc tieu
    is_full = _is_full_schema(conn, db_type)
    with _cursor(conn) as cur:
        if is_full:
            sql = _prepare_sql(
                "SELECT genres FROM genres WHERE book_id = %s AND votes > 0 ORDER BY votes DESC",
                db_type,
            )
            cur.execute(sql, [goodreads_id])
            rows = cur.fetchall()
            if not rows:
                sql_any = _prepare_sql(
                    "SELECT genres FROM genres WHERE book_id = %s ORDER BY votes DESC",
                    db_type,
                )
                cur.execute(sql_any, [goodreads_id])
                rows = cur.fetchall()
            return [str(_row_val(r, "genres", 0)) for r in rows if _row_val(r, "genres", 0)]

        sql = _prepare_sql("SELECT category FROM book_categories WHERE book_id = %s", db_type)
        cur.execute(sql, [goodreads_id])
        return [str(_row_val(r, "category", 0)) for r in cur.fetchall() if _row_val(r, "category", 0)]


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
    if _is_full_schema(conn, db_type):
        return _get_similar_books_full(
            conn, db_type, target_id, author_name, language,
            book_tag_terms, preferred_tag_terms, normalized_tags, limit,
        )

    # Tim cac cuon sach tuong dong theo the loai hoac tac gia (legacy)
    with _cursor(conn) as cur:
        if normalized_tags:
            placeholders = ", ".join(["%s"] * len(normalized_tags))
            score_parts = []
            score_params: List[Any] = []
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
            sql = f"""
                SELECT {_LEGACY_BOOK_COLUMNS}
                FROM books
                WHERE id <> %s AND (author_name = %s OR language = %s)
                ORDER BY CASE WHEN author_name = %s THEN 0 ELSE 1 END,
                         rating DESC, ratings_count DESC
                LIMIT %s
            """
            cur.execute(_prepare_sql(sql, db_type), [target_id, author_name, language, author_name, limit])
        return [_normalize_row(r) for r in cur.fetchall()]


def _get_similar_books_full(
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
    available_genres = _get_distinct_genres(conn, db_type)
    exact_book_genres = set(_match_genre_labels(book_tag_terms, available_genres))
    exact_pref_genres = set(_match_genre_labels(preferred_tag_terms, available_genres))
    all_target_genres = list(dict.fromkeys(_match_genre_labels(normalized_tags, available_genres)))

    candidate_ids: List[int] = []
    seen_ids = {int(target_id)}

    def _add_candidate(bid: Any) -> None:
        if bid is None:
            return
        bid_int = int(bid)
        if bid_int not in seen_ids:
            seen_ids.add(bid_int)
            candidate_ids.append(bid_int)

    with _cursor(conn) as cur:
        # 1. Sach cung tac gia
        cur.execute(
            _prepare_sql("SELECT author_id FROM book_authors_map WHERE book_id = %s", db_type),
            [target_id],
        )
        target_aids = [str(_row_val(r, "author_id", 0)) for r in cur.fetchall() if _row_val(r, "author_id", 0)]
        same_author_ids = set()
        if target_aids:
            a_ph = ", ".join(["%s"] * len(target_aids))
            cur.execute(
                _prepare_sql(
                    f"SELECT book_id FROM book_authors_map WHERE author_id IN ({a_ph}) LIMIT %s",
                    db_type,
                ),
                [*target_aids, max(limit * 4, 40)],
            )
            for r in cur.fetchall():
                bid = _row_val(r, "book_id", 0)
                if bid is not None and int(bid) != int(target_id):
                    same_author_ids.add(int(bid))
                    _add_candidate(bid)

        # 2. Ung vien theo tung genre su dung idx_genres_genre_votes (genres, votes)
        per_genre_cap = max(limit * 8, 60)
        for gname in all_target_genres[:6]:
            cur.execute(
                _prepare_sql(
                    "SELECT book_id FROM genres WHERE genres = %s AND votes > 0 ORDER BY votes DESC LIMIT %s",
                    db_type,
                ),
                [gname, per_genre_cap],
            )
            for r in cur.fetchall():
                _add_candidate(_row_val(r, "book_id", 0))

        # 3. Fallback theo language neu it ung vien
        if len(candidate_ids) < limit and language:
            cur.execute(
                _prepare_sql(
                    "SELECT book_id FROM books WHERE book_id <> %s AND language_code = %s "
                    "ORDER BY ratings_count DESC LIMIT %s",
                    db_type,
                ),
                [target_id, language, limit * 4],
            )
            for r in cur.fetchall():
                _add_candidate(_row_val(r, "book_id", 0))

        if not candidate_ids:
            return []

        capped_ids = candidate_ids[:300]
        ph = ", ".join(["%s"] * len(capped_ids))
        cur.execute(
            _prepare_sql(f"{_FULL_BOOK_SELECT} WHERE b.book_id IN ({ph})", db_type),
            capped_ids,
        )
        hydrated = _hydrate_full_books(cur, db_type, cur.fetchall())

    def _score(book: Dict[str, Any]) -> Tuple[int, int, float, int]:
        b_genres = set(book.get("tags") or [])
        tag_score = 2 * len(b_genres & exact_book_genres) + len(b_genres & exact_pref_genres)
        is_same_author = 1 if int(book["id"]) in same_author_ids else 0
        rating = float(book.get("rating") or 0)
        rc = int(book.get("ratings_count") or 0)
        return (tag_score, is_same_author, rating, rc)

    hydrated.sort(key=_score, reverse=True)
    return hydrated[:limit]


def get_sample_reviews(conn, db_type: str, goodreads_id: int, limit: int) -> List[Dict[str, Any]]:
    # Lay cac review mau cho cuon sach
    is_full = _is_full_schema(conn, db_type)
    table_name = "reviews" if is_full else "sample_reviews"
    sql = _prepare_sql(
        f"""
        SELECT review_id, user_id, rating, review_text, date_added
        FROM {table_name}
        WHERE book_id = %s
        ORDER BY date_added DESC
        LIMIT %s
        """,
        db_type,
    )
    with _cursor(conn) as cur:
        cur.execute(sql, [goodreads_id, limit])
        rows = [_normalize_row(r) for r in cur.fetchall()]
    for r in rows:
        dt = r.get("date_added")
        if isinstance(dt, (datetime, date)):
            r["date_added"] = dt.isoformat(sep=" ")
        elif dt is not None and not isinstance(dt, str):
            r["date_added"] = str(dt)
    return rows


def get_categories_summary(conn, db_type: str, limit: int = 50) -> List[Dict[str, Any]]:
    # Lay thong ke top the loai
    is_full = _is_full_schema(conn, db_type)
    key = _conn_cache_key(conn, db_type)
    if is_full and key is not None:
        with _TTL_CACHE_LOCK:
            hit = _CATEGORIES_SUMMARY_CACHE.get(key)
        if hit and (time.monotonic() - hit[0] < _MYSQL_CATALOG_CACHE_TTL):
            return hit[1][:limit]

    if is_full:
        sql = _prepare_sql(
            """
            SELECT genres AS category, COUNT(*) AS count
            FROM genres
            WHERE votes > 0
            GROUP BY genres
            ORDER BY count DESC
            LIMIT %s
            """,
            db_type,
        )
    else:
        sql = _prepare_sql(
            """
            SELECT category, COUNT(*) AS count
            FROM book_categories
            GROUP BY category
            ORDER BY count DESC
            LIMIT %s
            """,
            db_type,
        )
    with _cursor(conn) as cur:
        cur.execute(sql, [50 if (is_full and key is not None) else limit])
        rows = [_normalize_row(r) for r in cur.fetchall()]

    if is_full and key is not None:
        with _TTL_CACHE_LOCK:
            _CATEGORIES_SUMMARY_CACHE[key] = (time.monotonic(), rows)
        with _SCHEMA_CACHE_LOCK:
            if key not in _DISTINCT_GENRES_CACHE and rows:
                _DISTINCT_GENRES_CACHE[key] = [str(r["category"]) for r in rows if r.get("category")]
        return rows[:limit]
    return rows


def get_database_stats(conn, db_type: str) -> Dict[str, Any]:
    # Lay thong ke tong quat ve CSDL
    is_full = _is_full_schema(conn, db_type)
    key = _conn_cache_key(conn, db_type)
    if is_full and key is not None:
        with _TTL_CACHE_LOCK:
            hit = _STATS_CACHE.get(key)
        if hit and (time.monotonic() - hit[0] < _MYSQL_CATALOG_CACHE_TTL):
            return hit[1]

    with _cursor(conn) as cur:
        cur.execute("SELECT COUNT(*) AS total FROM books;")
        r1 = cur.fetchone()
        total = int(r1["total"] if isinstance(r1, dict) else r1[0])

        if is_full:
            cur.execute("SELECT COUNT(*) AS total FROM genres;")
            r2 = cur.fetchone()
            cat_total = int(r2["total"] if isinstance(r2, dict) else r2[0])
            cur.execute("SELECT AVG(average_rating) AS avg_rating FROM books WHERE ratings_count > 0;")
        else:
            cur.execute("SELECT COUNT(*) AS total FROM book_categories;")
            r2 = cur.fetchone()
            cat_total = int(r2["total"] if isinstance(r2, dict) else r2[0])
            cur.execute("SELECT AVG(rating) AS avg_rating FROM books WHERE ratings_count > 0;")

        r3 = cur.fetchone()
        avg_rating = r3["avg_rating"] if isinstance(r3, dict) else r3[0]

    stats = {
        "total_books": total,
        "total_category_tags": cat_total,
        "avg_rating": round(float(avg_rating or 0), 2),
    }
    if is_full and key is not None:
        with _TTL_CACHE_LOCK:
            _STATS_CACHE[key] = (time.monotonic(), stats)
    return stats
