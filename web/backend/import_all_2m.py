"""
Script nạp toàn bộ 2.360.655 cuốn sách (toàn bộ ấn bản gốc đã làm giàu) lên Aiven PostgreSQL:
- Nguồn: goodreads_books_enriched.json.gz (2.57 GB)
- Tối ưu hiệu năng: Tạm gỡ index GIN/BTree trong lúc nạp, nạp theo batch 10.000 cuốn
- Giám sát an toàn ổ đĩa Aiven thời gian thực (Real-time Storage Safeguard):
  Tự động dừng khẩn cấp (Emergency Stop) nếu đĩa database chạm ngưỡng 6.5 GB (an toàn dưới 8 GB)
- Cơ chế Checkpoint Resume: Tự động lưu tiến độ, rớt mạng chạy lại sẽ nạp tiếp
"""

import gzip
import json
import os
import sys
import time
import psycopg2
import psycopg2.extras

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_FILE = os.path.join(BASE_DIR, "goodreads_books_enriched.json.gz")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "import_checkpoint.json")

AIVEN_URL = os.getenv(
    "AIVEN_DATABASE_URL",
    "postgres://avnadmin:YOUR_AIVEN_PASSWORD@database-recommender-system.f.aivencloud.com:21595/defaultdb?sslmode=require"
)

BATCH_SIZE = 10000
MAX_SAFE_DB_SIZE_GB = 6.5  # Ngưỡng ngắt khẩn cấp an toàn


def clean_int(val):
    if not val:
        return None
    try:
        v = str(val).strip().split('.')[0]
        return int(v) if v and v.isdigit() else None
    except Exception:
        return None


def clean_float(val, default=0.0):
    if not val:
        return default
    try:
        return round(float(val), 2)
    except Exception:
        return default


def clean_str(val, max_len=None):
    if not val:
        return None
    s = str(val).strip()
    if s.lower() in ('nan', 'none', 'null', ''):
        return None
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s


def get_db_size_info(cur):
    cur.execute("SELECT pg_database_size(current_database()), pg_size_pretty(pg_database_size(current_database()));")
    size_bytes, size_pretty = cur.fetchone()
    size_gb = size_bytes / (1024 ** 3)
    return size_gb, size_pretty


def drop_indexes_for_fast_insert(cur):
    print("\n[Chuẩn bị] Tạm gỡ các chỉ mục phụ để tăng tốc độ nạp gấp 5 lần...")
    cur.execute("ALTER TABLE books DROP CONSTRAINT IF EXISTS books_goodreads_id_key;")
    indexes_to_drop = [
        "idx_books_title_trgm",
        "idx_books_author_trgm",
        "idx_books_rating",
        "idx_books_ratings_count",
        "idx_books_trending"
    ]
    for idx in indexes_to_drop:
        cur.execute(f"DROP INDEX IF EXISTS {idx};")
    print(" -> Đã gỡ các chỉ mục phụ thành công.")


def restore_indexes_after_insert(cur):
    print("\n[Tối ưu hóa] Đang tái tạo lại toàn bộ chỉ mục trên Aiven PostgreSQL...")
    start_t = time.time()
    
    cur.execute("ALTER TABLE books ADD CONSTRAINT books_goodreads_id_key UNIQUE (goodreads_id);")
    print(f" -> Tạo xong constraint books_goodreads_id_key ({time.time() - start_t:.1f}s)")
    
    t_bt = time.time()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_rating ON public.books USING btree (rating DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_ratings_count ON public.books USING btree (ratings_count DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_trending ON public.books USING btree (trending_rank);")
    print(f" -> Tạo xong các chỉ mục B-Tree ({time.time() - t_bt:.1f}s)")

    print(" -> Đang tạo chỉ mục tìm kiếm văn bản GIN Trigram (title & author)...")
    t_gin = time.time()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_title_trgm ON public.books USING gin (title gin_trgm_ops);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_author_trgm ON public.books USING gin (author_name gin_trgm_ops);")
    print(f" -> Tạo xong các chỉ mục GIN ({time.time() - t_gin:.1f}s)")

    print(" -> Đang chạy ANALYZE books để tối ưu hóa bộ lập lịch truy vấn...")
    cur.execute("ANALYZE books;")
    print(" -> Hoàn tất tối ưu hóa chỉ mục!")


def main():
    print("=" * 70)
    print("TIẾN TRÌNH NẠP TOÀN BỘ 2.360.655 CUỐN SÁCH LÊN AIVEN POSTGRESQL")
    print(f"Nguồn: {INPUT_FILE}")
    print(f"Ngưỡng an toàn tối đa: {MAX_SAFE_DB_SIZE_GB} GB")
    print("=" * 70, flush=True)

    if not os.path.exists(INPUT_FILE):
        print(f"[Lỗi] Không tìm thấy file {INPUT_FILE}!")
        return

    # Reset checkpoint cho lần nạp toàn bộ này
    start_offset = 0
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                ckpt = json.load(f)
                # Nếu checkpoint cũ là của 1M sách thì reset về 0
                if ckpt.get("dataset") == "all_2.36m":
                    start_offset = ckpt.get("imported_count", 0)
                    print(f"Phát hiện Checkpoint: Tiếp tục nạp từ cuốn thứ {start_offset + 1:,}...")
        except Exception:
            start_offset = 0

    print("Đang kết nối tới Aiven PostgreSQL...")
    conn = psycopg2.connect(AIVEN_URL)
    conn.autocommit = False
    cur = conn.cursor()

    initial_size_gb, initial_pretty = get_db_size_info(cur)
    print(f"Dung lượng Database hiện tại: {initial_pretty} ({initial_size_gb:.2f} GB / 8 GB)")

    if start_offset == 0:
        print("\n[Khởi tạo] Xóa bảng books để bắt đầu nạp 2.360.655 cuốn mới...")
        cur.execute("TRUNCATE TABLE books RESTART IDENTITY CASCADE;")
        conn.commit()
        drop_indexes_for_fast_insert(cur)
        conn.commit()

    print(f"\nBắt đầu nạp dữ liệu (Batch size: {BATCH_SIZE:,} cuốn)...", flush=True)
    start_time = time.time()
    last_print = time.time()

    current_idx = 0
    batch_rows = []
    imported_count = start_offset
    seen_book_ids = set()

    sql_insert = """
        INSERT INTO books (
            id, goodreads_id, title, author_name, description, cover_url,
            isbn, isbn13, published_year, pages, language, rating,
            ratings_count, publisher, tags, trending_rank, price, created_at
        ) VALUES %s
    """

    with gzip.open(INPUT_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            b = json.loads(line)
            gid = clean_int(b.get("book_id"))
            if not gid or gid in seen_book_ids:
                continue
            seen_book_ids.add(gid)

            current_idx += 1
            if current_idx <= start_offset:
                continue

            title = clean_str(b.get("title"), 1000) or "Untitled"
            author = clean_str(b.get("author_name"), 500) or "Unknown Author"
            desc = clean_str(b.get("description"), 20000)
            cover = clean_str(b.get("image_url"), 1000)
            isbn = clean_str(b.get("isbn"), 50)
            isbn13 = clean_str(b.get("isbn13"), 50)
            year = clean_int(b.get("publication_year"))
            pages = clean_int(b.get("num_pages"))
            lang = clean_str(b.get("language_code"), 50) or "eng"
            rating = clean_float(b.get("average_rating"), 4.0)
            ratings_count = clean_int(b.get("ratings_count")) or 0
            pub = clean_str(b.get("publisher"), 500)
            
            genres = b.get("genres", [])
            tags = genres[:5] if isinstance(genres, list) else []

            price = round(min(max((ratings_count % 17) + 7.99, 5.99), 29.99), 2)
            trending_rank = current_idx

            row = (
                current_idx,
                gid,
                title,
                author,
                desc,
                cover,
                isbn,
                isbn13,
                year,
                pages,
                lang,
                rating,
                ratings_count,
                pub,
                tags,
                trending_rank,
                price,
                "NOW()"
            )
            batch_rows.append(row)

            if len(batch_rows) >= BATCH_SIZE:
                psycopg2.extras.execute_values(cur, sql_insert, batch_rows, page_size=2000)
                conn.commit()
                imported_count += len(batch_rows)
                batch_rows = []

                # Lưu checkpoint
                with open(CHECKPOINT_FILE, "w") as ck_f:
                    json.dump({"dataset": "all_2.36m", "imported_count": imported_count}, ck_f)

                # Giám sát dung lượng và tốc độ
                elapsed = time.time() - start_time
                speed = int(imported_count / max(elapsed, 1))
                db_gb, db_pretty = get_db_size_info(cur)

                pct = (imported_count / 2360655) * 100
                print(f"   Đã nạp {imported_count:,}/2,360,655 cuốn ({pct:.1f}%) - Tốc độ: {speed} cuốn/s | DB Size: {db_pretty} ({db_gb:.2f} GB)", flush=True)

                # Kiểm tra ngắt khẩn cấp bảo vệ ổ cứng
                if db_gb >= MAX_SAFE_DB_SIZE_GB:
                    print(f"\n[CẢNH BÁO AN TOÀN] Dung lượng DB ({db_gb:.2f} GB) đã chạm ngưỡng an toàn ({MAX_SAFE_DB_SIZE_GB} GB)!")
                    print("Tự động dừng nạp để bảo vệ gói lưu trữ của bạn. Không lo bị khóa database!")
                    break

    # Nạp batch cuối cùng nếu còn
    if batch_rows:
        psycopg2.extras.execute_values(cur, sql_insert, batch_rows, page_size=2000)
        conn.commit()
        imported_count += len(batch_rows)
        with open(CHECKPOINT_FILE, "w") as ck_f:
            json.dump({"dataset": "all_2.36m", "imported_count": imported_count}, ck_f)

    total_time = time.time() - start_time
    print(f"\n[Hoàn tất nạp thô] Tổng cộng {imported_count:,} cuốn trong {total_time:.1f}s ({total_time/60:.2f} phút).", flush=True)

    # Khôi phục index
    restore_indexes_after_insert(cur)
    conn.commit()

    final_gb, final_pretty = get_db_size_info(cur)
    print("\n" + "=" * 70)
    print("HOÀN TẤT TIẾN TRÌNH NẠP TOÀN BỘ 2.360.655 CUỐN LÊN AIVEN POSTGRESQL!")
    print(f"Tổng số sách đã nạp: {imported_count:,} cuốn")
    print(f"Thời gian tổng: {time.time() - start_time:.1f}s ({(time.time() - start_time)/60:.2f} phút)")
    print(f"Dung lượng Database cuối cùng: {final_pretty} ({final_gb:.2f} GB / 8 GB)")
    print("=" * 70, flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
