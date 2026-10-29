"""
Script làm giàu siêu dữ liệu sách (Metadata Enrichment):
1. Nguồn 1: Stream từ file dump raw Goodreads (goodreads_books.json.gz) trên máy (2.36M sách)
2. Nguồn 2: Open Library API cho những cuốn còn thiếu
3. Cập nhật trực tiếp vào Aiven PostgreSQL: isbn, isbn13, pages, published_year, publisher, language, description
"""

import os
import sys
import gzip
import json
import time
import urllib.request
import urllib.parse
import psycopg2
import psycopg2.extras

# UTF-8 stdout trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

AIVEN_URL = os.getenv(
    "AIVEN_DATABASE_URL",
    "postgres://avnadmin:YOUR_AIVEN_PASSWORD@database-recommender-system.f.aivencloud.com:21595/defaultdb?sslmode=require"
)

# Đường dẫn file dump trên máy
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENRICHED_DUMP = os.path.join(BASE_DIR, "goodreads_books_enriched.json.gz")
RAW_DUMP = os.path.join(BASE_DIR, "goodreads_books.json.gz")
DUMP_PATH = ENRICHED_DUMP if os.path.exists(ENRICHED_DUMP) else RAW_DUMP



def clean_int(val):
    if not val:
        return None
    try:
        v = str(val).strip().split('.')[0]
        return int(v) if v and v.isdigit() else None
    except Exception:
        return None


def clean_str(val):
    if not val:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ('nan', 'none', 'null', '') else None


def enrich_from_local_dump(conn, missing_books):
    """
    missing_books: dict {goodreads_id: {'id': db_id, 'title': title, 'author': author, 'desc': desc}}
    """
    if not os.path.exists(DUMP_PATH):
        print(f"[Warning] Không tìm thấy file dump tại {DUMP_PATH}")
        return {}

    print(f"\n[Giai đoạn 1] Quét file dump nội bộ: {DUMP_PATH}")
    print(f"Cần tìm thông tin cho {len(missing_books)} cuốn sách...")

    target_gids = set(missing_books.keys())
    matched_updates = []
    start_time = time.time()
    line_count = 0
    import re
    re_bid = re.compile(r'"book_id":\s*"(\d+)"')

    with gzip.open(DUMP_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            line_count += 1
            if line_count % 200000 == 0:
                elapsed = time.time() - start_time
                print(f"  -> Đã duyệt {line_count:,} dòng dump ({len(matched_updates)}/{len(missing_books)} sách khớp, {elapsed:.1f}s)...")

            m = re_bid.search(line)
            if m:
                b_id = m.group(1)
                if b_id in target_gids:
                    target_gids.remove(b_id)
                    try:
                        data = json.loads(line)
                        db_info = missing_books[b_id]

                        isbn = clean_str(data.get("isbn"))
                        isbn13 = clean_str(data.get("isbn13"))
                        pages = clean_int(data.get("num_pages"))
                        pub_year = clean_int(data.get("publication_year"))
                        publisher = clean_str(data.get("publisher"))
                        lang = clean_str(data.get("language_code"))
                        desc = clean_str(data.get("description"))

                        matched_updates.append((
                            isbn,
                            isbn13,
                            pages,
                            pub_year,
                            publisher,
                            lang or 'en',
                            desc if not db_info['has_desc'] else None,
                            db_info['id']
                        ))
                    except Exception:
                        pass

            if not target_gids:
                print(f"[Success] Đã tìm thấy toàn bộ {len(missing_books)} cuốn sách từ file dump!")
                break

    print(f"[Giai đoạn 1 Hoàn tất] Tìm thấy {len(matched_updates)}/{len(missing_books)} cuốn trong {time.time() - start_time:.1f} giây.")

    if matched_updates:
        print(f"Đang cập nhật {len(matched_updates)} bản ghi vào Aiven PostgreSQL...")
        cur = conn.cursor()
        sql = """
            UPDATE books
            SET isbn = COALESCE(%s, isbn),
                isbn13 = COALESCE(%s, isbn13),
                pages = COALESCE(%s, pages),
                published_year = COALESCE(%s, published_year),
                publisher = COALESCE(%s, publisher),
                language = COALESCE(%s, language),
                description = COALESCE(%s, description)
            WHERE id = %s
        """
        psycopg2.extras.execute_batch(cur, sql, matched_updates, page_size=500)
        conn.commit()
        print("[Database] Đã lưu thành công dữ liệu từ dump vào Aiven PostgreSQL.")

    return target_gids  # trả về các gid chưa tìm thấy


def query_open_library(title, author):
    """
    Gọi Open Library Search API để lấy metadata cho một cuốn sách.
    """
    try:
        params = {"title": title, "limit": 1}
        if author:
            params["author"] = author
        url = f"https://openlibrary.org/search.json?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BookRecommenderSystem/1.0 (contact: student@recommender.local)"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                docs = data.get("docs", [])
                if docs:
                    doc = docs[0]
                    isbns = doc.get("isbn", [])
                    isbn = clean_str(isbns[0]) if isbns else None
                    isbn13 = None
                    for ib in isbns:
                        if len(ib) == 13:
                            isbn13 = ib
                            break

                    pages = clean_int(doc.get("number_of_pages_median"))
                    pub_year = clean_int(doc.get("first_publish_year"))
                    publishers = doc.get("publisher", [])
                    publisher = clean_str(publishers[0]) if publishers else None

                    return {
                        "isbn": isbn,
                        "isbn13": isbn13,
                        "pages": pages,
                        "published_year": pub_year,
                        "publisher": publisher,
                    }
    except Exception as e:
        # Có thể bị timeout hoặc rate limit
        pass
    return None


def enrich_from_open_library(conn, remaining_gids, missing_books, max_calls=50):
    """
    Bổ sung các cuốn còn thiếu qua Open Library API (giới hạn số request để tránh block).
    """
    if not remaining_gids:
        return

    print(f"\n[Giai đoạn 2] Gọi Open Library API cho các cuốn còn lại (tối đa {max_calls} cuốn)...")
    updates = []
    count = 0

    for gid in list(remaining_gids)[:max_calls]:
        info = missing_books[gid]
        title = info["title"]
        author = info["author"]

        meta = query_open_library(title, author)
        if meta and (meta["isbn"] or meta["pages"] or meta["published_year"] or meta["publisher"]):
            count += 1
            print(f"  + Khớp Open Library: '{title[:35]}...' -> {meta['pages']} trang, NXB: {meta['publisher']}")
            updates.append((
                meta["isbn"],
                meta["isbn13"],
                meta["pages"],
                meta["published_year"],
                meta["publisher"],
                info["id"]
            ))

        time.sleep(0.3)  # tôn trọng rate limit Open Library

    if updates:
        print(f"Đang lưu {len(updates)} bản ghi từ Open Library vào PostgreSQL...")
        cur = conn.cursor()
        sql = """
            UPDATE books
            SET isbn = COALESCE(%s, isbn),
                isbn13 = COALESCE(%s, isbn13),
                pages = COALESCE(%s, pages),
                published_year = COALESCE(%s, published_year),
                publisher = COALESCE(%s, publisher)
            WHERE id = %s
        """
        psycopg2.extras.execute_batch(cur, sql, updates, page_size=100)
        conn.commit()
        print("[Database] Cập nhật thành công từ Open Library.")


def main():
    print("=== BẮT ĐẦU LÀM GIÀU SIÊU DỮ LIỆU SÁCH (METADATA ENRICHMENT) ===")
    conn = psycopg2.connect(AIVEN_URL)
    cur = conn.cursor()

    # Lấy danh sách các cuốn sách đang khuyết isbn, pages, published_year, publisher
    cur.execute("""
        SELECT id, goodreads_id, title, author_name, description
        FROM books
        WHERE goodreads_id IS NOT NULL 
          AND (isbn IS NULL OR pages IS NULL OR published_year IS NULL OR publisher IS NULL)
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    print(f"[Database] Đã tìm thấy {len(rows)} cuốn sách đang khuyết thông tin.")

    if not rows:
        print("Tất cả sách đều đã có đủ thông tin!")
        return

    missing_books = {}
    for r in rows:
        missing_books[str(r[1])] = {
            "id": r[0],
            "title": r[2],
            "author": r[3],
            "has_desc": bool(r[4])
        }

    # Giai đoạn 1: Quét file dump Goodreads
    remaining = enrich_from_local_dump(conn, missing_books)

    # Giai đoạn 2: Gọi Open Library cho các cuốn còn lại
    if remaining:
        enrich_from_open_library(conn, remaining, missing_books, max_calls=30)

    # Thống kê kết quả sau làm giàu
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(description) as has_desc,
            COUNT(cover_url) as has_cover,
            COUNT(isbn) as has_isbn,
            COUNT(isbn13) as has_isbn13,
            COUNT(published_year) as has_pub_year,
            COUNT(pages) as has_pages,
            COUNT(publisher) as has_publisher
        FROM books
    """)
    s = cur.fetchone()
    total = s[0]
    print("\n" + "=" * 50)
    print("=== KẾT QUẢ SAU KHI LÀM GIÀU METADATA ===")
    print(f"Tổng số sách:            {total:,}")
    print(f"Có Mã ISBN:              {s[3]:,} ({s[3]*100/total:.1f}%)")
    print(f"Có Mã ISBN-13:           {s[4]:,} ({s[4]*100/total:.1f}%)")
    print(f"Có Năm xuất bản:         {s[5]:,} ({s[5]*100/total:.1f}%)")
    print(f"Có Số trang:             {s[6]:,} ({s[6]*100/total:.1f}%)")
    print(f"Có Nhà xuất bản:         {s[7]:,} ({s[7]*100/total:.1f}%)")
    print(f"Có Mô tả:                {s[1]:,} ({s[1]*100/total:.1f}%)")
    print("=" * 50)
    conn.close()


if __name__ == "__main__":
    main()
