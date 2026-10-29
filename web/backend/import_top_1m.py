"""
Script nạp 1.000.000 cuốn sách Top xuất sắc nhất lên Aiven PostgreSQL:
- Nguồn: goodreads_books_dedup_1m.json.gz
- Tối ưu hiệu năng: Tạm gỡ index GIN/BTree trong lúc nạp, nạp theo batch 10.000 cuốn
- Giám sát an toàn ổ đĩa Aiven thời gian thực (Real-time Storage Safeguard):
  Tự động dừng khẩn cấp (Emergency Stop) nếu đĩa database chạm ngưỡng 6.2 GB
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
INPUT_FILE = os.path.join(BASE_DIR, "goodreads_books_dedup_1m.json.gz")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "import_checkpoint.json")

AIVEN_URL = os.getenv(
    "AIVEN_DATABASE_URL",
    "postgres://avnadmin:YOUR_AIVEN_PASSWORD@database-recommender-system.f.aivencloud.com:21595/defaultdb?sslmode=require"
)

BATCH_SIZE = 10000
MAX_SAFE_DB_SIZE_GB = 6.2  # Dừng khẩn cấp nếu DB vượt quá 6.2 GB để bảo vệ gói 8 GB Aiven


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
    
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_rating ON public.books USING btree (rating DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_ratings_count ON public.books USING btree (ratings_count DESC);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_trending ON public.books USING btree (trending_rank);")
    print(f" -> Tạo xong các chỉ mục B-Tree ({time.time() - start_t:.1f}s)")

    print(" -> Đang tạo chỉ mục tìm kiếm văn bản GIN Trigram (title & author)...")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_title_trgm ON public.books USING gin (title gin_trgm_ops);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_books_author_trgm ON public.books USING gin (author_name gin_trgm_ops);")
    print(f" -> Tạo xong các chỉ mục GIN ({time.time() - start_t:.1f}s)")

    print(" -> Đang chạy ANALYZE books để tối ưu hóa bộ lập lịch truy vấn...")
    cur.execute("ANALYZE books;")
    print(" -> Hoàn tất tối ưu hóa chỉ mục!")



def run_import():
    if not os.path.exists(INPUT_FILE):
        print(f"Lỗi: Không tìm thấy tệp {INPUT_FILE}!")
        return

    print("=" * 70)
    print("TIẾN TRÌNH NẠP 1.000.000 CUỐN SÁCH LÊN AIVEN POSTGRESQL")
    print(f"Nguồn: {INPUT_FILE}")
    print(f"Ngưỡng an toàn tối đa: {MAX_SAFE_DB_SIZE_GB} GB")
    print("=" * 70, flush=True)

    # Đọc checkpoint nếu có
    start_offset = 0
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE, "r") as f:
                ckpt = json.load(f)
                start_offset = ckpt.get("imported_count", 0)
                print(f"Phát hiện Checkpoint: Sẽ tiếp tục nạp từ cuốn thứ {start_offset + 1:,}...")
        except Exception:
            start_offset = 0

    print("Đang kết nối tới Aiven PostgreSQL...")
    conn = psycopg2.connect(AIVEN_URL)
    conn.autocommit = False
    cur = conn.cursor()

    initial_size_gb, initial_pretty = get_db_size_info(cur)
    print(f"Dung lượng Database hiện tại: {initial_pretty} ({initial_size_gb:.2f} GB / 8 GB)")

    # Nếu bắt đầu từ đầu, xóa sạch bảng books cũ để nạp mới từ id=1
    if start_offset == 0:
        print("\n[Khởi tạo] Xóa dữ liệu cũ trong bảng books để nạp 1.000.000 cuốn mới...")
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

    sql_insert = """
        INSERT INTO books (
            id, goodreads_id, title, author_name, description, cover_url,
            isbn, isbn13, published_year, pages, language, rating,
            ratings_count, publisher, tags, trending_rank, price, created_at
        ) VALUES %s
    """

    with gzip.open(INPUT_FILE, "rt", encoding="utf-8") as f:
        for line in f:
            current_idx += 1
            if current_idx <= start_offset:
                continue

            b = json.loads(line)
            
            gid = clean_int(b.get("book_id"))
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

            # Giá bán giả định logic từ $5.99 đến $29.99
            price = round(min(max((ratings_count % 17) + 7.99, 5.99), 29.99), 2)
            trending_rank = current_idx  # Xếp hạng theo độ phổ biến giảm dần

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
                    json.dump({"imported_count": imported_count}, ck_f)

                # Kiểm tra dung lượng đĩa Aiven
                cur_size_gb, cur_size_pretty = get_db_size_info(cur)
                elapsed = time.time() - start_time
                speed = (imported_count - start_offset) / elapsed if elapsed > 0 else 0
                pct = (imported_count / 1000000) * 100

                print(f"   Đã nạp {imported_count:,}/1,000,000 cuốn ({pct:.1f}%) - Tốc độ: {speed:.0f} cuốn/s | DB Size: {cur_size_pretty} ({cur_size_gb:.2f} GB)", flush=True)

                # Cơ chế dừng khẩn cấp nếu đĩa chạm ngưỡng nguy hiểm
                if cur_size_gb >= MAX_SAFE_DB_SIZE_GB:
                    print(f"\n[CẢNH BÁO AN TOÀN] Database đã chạm ngưỡng an toàn tối đa {MAX_SAFE_DB_SIZE_GB} GB!")
                    print(f"Tự động dừng tiến trình nạp tại cuốn thứ {imported_count:,} để bảo vệ ổ đĩa Aiven!")
                    break

        # Nạp nốt mẻ cuối nếu còn
        if batch_rows:
            psycopg2.extras.execute_values(cur, sql_insert, batch_rows, page_size=2000)
            conn.commit()
            imported_count += len(batch_rows)
            with open(CHECKPOINT_FILE, "w") as ck_f:
                json.dump({"imported_count": imported_count}, ck_f)

    # Tái tạo chỉ mục
    restore_indexes_after_insert(cur)
    conn.commit()

    final_size_gb, final_size_pretty = get_db_size_info(cur)
    total_time = time.time() - start_time

    print("\n" + "=" * 70)
    print("HOÀN TẤT TIẾN TRÌNH NẠP DỮ LIỆU LÊN AIVEN POSTGRESQL!")
    print(f"Tổng số sách đã nạp: {imported_count:,} cuốn")
    print(f"Thời gian nạp: {total_time:.1f}s (~{total_time/60:.2f} phút)")
    print(f"Dung lượng Database cuối cùng: {final_size_pretty} ({final_size_gb:.2f} GB / 8 GB)")
    print("=" * 70, flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    run_import()
