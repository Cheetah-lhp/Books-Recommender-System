"""
Pipeline làm giàu dữ liệu gốc: goodreads_books.json.gz (2.36 triệu cuốn)
- Hợp nhất tên tác giả từ goodreads_book_authors.json.gz
- Hợp nhất thể loại từ goodreads_book_genres_initial.json.gz
- Bổ sung năm xuất bản gốc từ goodreads_book_works.json.gz
- Nội suy thông tin tác phẩm (Work-Level Cross-Edition Propagation) cho description, pages, publisher
- Tự động thay thế ảnh bìa xám nophoto bằng Open Library Cover CDN
- Tối ưu hiệu năng: compresslevel=1, cache work_profiles, flush=True
- Xuất ra tệp kết quả: goodreads_books_enriched.json.gz
"""

import gzip
import json
import os
import pickle
import sys
import time
import psutil

# Đảm bảo in UTF-8 không lỗi charmap trên Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BOOKS_RAW_PATH = os.path.join(BASE_DIR, "goodreads_books.json.gz")
AUTHORS_PATH = os.path.join(BASE_DIR, "goodreads_book_authors.json.gz")
GENRES_PATH = os.path.join(BASE_DIR, "goodreads_book_genres_initial.json.gz")
WORKS_PATH = os.path.join(BASE_DIR, "goodreads_book_works.json.gz")
OUTPUT_PATH = os.path.join(BASE_DIR, "goodreads_books_enriched.json.gz")
WORK_PROFILES_CACHE = os.path.join(BASE_DIR, "work_profiles_cache.pkl")


def get_ram_usage_mb():
    p = psutil.Process(os.getpid())
    return p.memory_info().rss / (1024 * 1024)


def load_authors():
    print("[1/5] Đang nạp danh mục tác giả từ goodreads_book_authors.json.gz...", flush=True)
    start_t = time.time()
    authors_map = {}
    with gzip.open(AUTHORS_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            authors_map[d["author_id"]] = d.get("name", "").strip()
    print(f" -> Đã nạp {len(authors_map):,} tác giả ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)", flush=True)
    return authors_map


def load_works():
    print("[2/5] Đang nạp danh mục tác phẩm từ goodreads_book_works.json.gz...", flush=True)
    start_t = time.time()
    works_year_map = {}
    with gzip.open(WORKS_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            w_id = d.get("work_id")
            orig_year = d.get("original_publication_year", "").strip()
            if w_id and orig_year:
                works_year_map[w_id] = orig_year
    print(f" -> Đã nạp {len(works_year_map):,} tác phẩm có năm gốc ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)", flush=True)
    return works_year_map


def build_work_profiles():
    """
    Pass 1: Quét xây dựng hồ sơ tác phẩm (Work-Level Profiles).
    Nếu đã có cache work_profiles_cache.pkl thì nạp tức thì trong 2 giây!
    """
    if os.path.exists(WORK_PROFILES_CACHE):
        print(f"[3/5] Phát hiện bộ đệm hồ sơ tác phẩm: {WORK_PROFILES_CACHE}. Đang nạp...", flush=True)
        start_t = time.time()
        with open(WORK_PROFILES_CACHE, "rb") as f:
            work_profiles = pickle.load(f)
        print(f" -> Đã nạp {len(work_profiles):,} hồ sơ tác phẩm từ bộ đệm ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)", flush=True)
        return work_profiles

    print("[3/5] Pass 1: Quét xây dựng hồ sơ tác phẩm (Work-Level Profiles)...", flush=True)
    start_t = time.time()
    work_profiles = {}  # work_id -> {desc, publisher, pages, cover, isbn13}
    count = 0

    with gzip.open(BOOKS_RAW_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            count += 1
            if count % 250000 == 0:
                print(f"   Đã quét {count:,}/2,360,655 cuốn... ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)", flush=True)

            d = json.loads(line)
            w_id = d.get("work_id")
            if not w_id:
                continue

            desc = d.get("description", "").strip()
            pub = d.get("publisher", "").strip()
            pages = d.get("num_pages", "").strip()
            img = d.get("image_url", "").strip()
            is_valid_img = img and "nophoto" not in img
            isbn13 = d.get("isbn13", "").strip()

            if w_id not in work_profiles:
                work_profiles[w_id] = {
                    "desc": desc,
                    "pub": pub,
                    "pages": pages,
                    "cover": img if is_valid_img else "",
                    "isbn13": isbn13,
                }
            else:
                prof = work_profiles[w_id]
                if len(desc) > len(prof["desc"]):
                    prof["desc"] = desc
                if not prof["pub"] and pub:
                    prof["pub"] = pub
                if not prof["pages"] and pages:
                    prof["pages"] = pages
                if not prof["cover"] and is_valid_img:
                    prof["cover"] = img
                if not prof["isbn13"] and isbn13:
                    prof["isbn13"] = isbn13

    print(f" -> Đã tổng hợp hồ sơ cho {len(work_profiles):,} tác phẩm ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)", flush=True)
    
    # Lưu cache để nếu cần chạy lại thì nạp tức thì
    print("   Đang lưu bộ đệm work_profiles_cache.pkl để tái sử dụng nhanh...", flush=True)
    try:
        with open(WORK_PROFILES_CACHE, "wb") as f:
            pickle.dump(work_profiles, f, protocol=pickle.HIGHEST_PROTOCOL)
        print("   -> Đã lưu bộ đệm thành công.", flush=True)
    except Exception as e:
        print(f"   (Bỏ qua lưu cache: {e})", flush=True)

    return work_profiles


def process_and_enrich():
    authors_map = load_authors()
    works_year_map = load_works()
    work_profiles = build_work_profiles()

    print("[4/5] Pass 2: Tiến hành làm giàu dữ liệu và ghi ra tệp goodreads_books_enriched.json.gz (Nén siêu tốc compresslevel=1)...", flush=True)
    start_t = time.time()

    stats_before = {
        "total": 0,
        "missing_isbn": 0,
        "missing_isbn13": 0,
        "missing_year": 0,
        "missing_pages": 0,
        "missing_publisher": 0,
        "missing_desc": 0,
        "nophoto": 0,
        "missing_author_name": 0,
        "missing_genres": 0,
    }

    stats_after = {
        "total": 0,
        "missing_isbn": 0,
        "missing_isbn13": 0,
        "missing_year": 0,
        "missing_pages": 0,
        "missing_publisher": 0,
        "missing_desc": 0,
        "nophoto": 0,
        "missing_author_name": 0,
        "missing_genres": 0,
    }

    enriched_counts = {
        "author_mapped": 0,
        "genres_mapped": 0,
        "year_from_work": 0,
        "desc_from_work": 0,
        "pages_from_work": 0,
        "pub_from_work": 0,
        "cover_from_work": 0,
        "cover_from_ol": 0,
    }

    temp_output_path = OUTPUT_PATH + ".tmp"

    with gzip.open(BOOKS_RAW_PATH, "rt", encoding="utf-8") as f_books, \
         gzip.open(GENRES_PATH, "rt", encoding="utf-8") as f_genres, \
         gzip.open(temp_output_path, "wt", compresslevel=1, encoding="utf-8") as f_out:

        for line_b in f_books:
            line_g = f_genres.readline()

            book = json.loads(line_b)
            genre_data = json.loads(line_g) if line_g else {}

            stats_before["total"] += 1
            stats_after["total"] += 1

            raw_isbn = book.get("isbn", "").strip()
            raw_isbn13 = book.get("isbn13", "").strip()
            raw_year = book.get("publication_year", "").strip()
            raw_pages = book.get("num_pages", "").strip()
            raw_pub = book.get("publisher", "").strip()
            raw_desc = book.get("description", "").strip()
            raw_img = book.get("image_url", "").strip()
            raw_authors = book.get("authors", [])

            if not raw_isbn: stats_before["missing_isbn"] += 1
            if not raw_isbn13: stats_before["missing_isbn13"] += 1
            if not raw_year: stats_before["missing_year"] += 1
            if not raw_pages: stats_before["missing_pages"] += 1
            if not raw_pub: stats_before["missing_publisher"] += 1
            if not raw_desc: stats_before["missing_desc"] += 1
            if not raw_img or "nophoto" in raw_img: stats_before["nophoto"] += 1
            stats_before["missing_author_name"] += 1
            stats_before["missing_genres"] += 1

            w_id = book.get("work_id")
            w_prof = work_profiles.get(w_id, {})

            # 1. Map tên tác giả
            author_names = []
            for a in raw_authors:
                a_id = a.get("author_id")
                name = authors_map.get(a_id, "")
                if name:
                    author_names.append(name)
            
            book["author_names"] = author_names
            book["author_name"] = author_names[0] if author_names else ""
            if author_names:
                enriched_counts["author_mapped"] += 1

            # 2. Map thể loại
            genres_dict = genre_data.get("genres", {})
            sorted_genres = sorted(genres_dict.keys(), key=lambda k: genres_dict[k], reverse=True)
            book["genres"] = sorted_genres
            book["primary_genre"] = sorted_genres[0] if sorted_genres else ""
            if sorted_genres:
                enriched_counts["genres_mapped"] += 1

            # 3. Làm giàu Năm xuất bản
            final_year = raw_year
            if not final_year:
                if w_id and w_id in works_year_map:
                    final_year = works_year_map[w_id]
                    enriched_counts["year_from_work"] += 1
                elif w_prof.get("year"):
                    final_year = w_prof["year"]
            book["publication_year"] = final_year

            # 4. Làm giàu Mô tả sách (Description)
            final_desc = raw_desc
            if not final_desc and w_prof.get("desc"):
                final_desc = w_prof["desc"]
                enriched_counts["desc_from_work"] += 1
            book["description"] = final_desc

            # 5. Làm giàu Số trang (num_pages)
            final_pages = raw_pages
            if not final_pages and w_prof.get("pages"):
                final_pages = w_prof["pages"]
                enriched_counts["pages_from_work"] += 1
            book["num_pages"] = final_pages

            # 6. Làm giàu Nhà xuất bản (publisher)
            final_pub = raw_pub
            if not final_pub and w_prof.get("pub"):
                final_pub = w_prof["pub"]
                enriched_counts["pub_from_work"] += 1
            book["publisher"] = final_pub

            # 7. Làm giàu Ảnh bìa (image_url)
            final_img = raw_img
            is_nophoto = not final_img or "nophoto" in final_img
            if is_nophoto:
                if w_prof.get("cover"):
                    final_img = w_prof["cover"]
                    enriched_counts["cover_from_work"] += 1
                elif raw_isbn13 or raw_isbn or w_prof.get("isbn13"):
                    lookup_isbn = raw_isbn13 or raw_isbn or w_prof.get("isbn13")
                    final_img = f"https://covers.openlibrary.org/b/isbn/{lookup_isbn}-L.jpg?default=false"
                    enriched_counts["cover_from_ol"] += 1
            book["image_url"] = final_img

            # Thống kê sau khi làm giàu
            if not book.get("isbn"): stats_after["missing_isbn"] += 1
            if not book.get("isbn13"): stats_after["missing_isbn13"] += 1
            if not book.get("publication_year"): stats_after["missing_year"] += 1
            if not book.get("num_pages"): stats_after["missing_pages"] += 1
            if not book.get("publisher"): stats_after["missing_publisher"] += 1
            if not book.get("description"): stats_after["missing_desc"] += 1
            cur_img = book.get("image_url", "")
            if not cur_img or "nophoto" in cur_img: stats_after["nophoto"] += 1
            if not book.get("author_name"): stats_after["missing_author_name"] += 1
            if not book.get("genres"): stats_after["missing_genres"] += 1

            f_out.write(json.dumps(book, ensure_ascii=False) + "\n")

            if stats_after["total"] % 200000 == 0:
                elapsed = time.time() - start_t
                speed = stats_after["total"] / elapsed if elapsed > 0 else 0
                pct = (stats_after["total"] / 2360655) * 100
                print(f"   Đã xử lý & ghi {stats_after['total']:,}/2,360,655 cuốn ({pct:.1f}%) - Tốc độ: {speed:.0f} cuốn/giây, RAM: {get_ram_usage_mb():.1f} MB", flush=True)

    if os.path.exists(OUTPUT_PATH):
        os.remove(OUTPUT_PATH)
    os.rename(temp_output_path, OUTPUT_PATH)

    total_time = time.time() - start_t
    print(f"\n[5/5] HOÀN TẤT LÀM GIÀU DỮ LIỆU ({total_time:.1f} giây, ~{total_time/60:.2f} phút)!", flush=True)
    print(f"File đầu ra: {OUTPUT_PATH}", flush=True)
    out_size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"Kích thước file enriched: {out_size_mb:.2f} MB\n", flush=True)

    total = stats_before["total"]
    print("=" * 75, flush=True)
    print(f"{'CHỈ SỐ THỐNG KÊ':<28} | {'GỐC (TRƯỚC)':<18} | {'SAU KHI LÀM GIÀU':<20}", flush=True)
    print("=" * 75, flush=True)

    metrics = [
        ("Tên tác giả (author_name)", total - stats_before["missing_author_name"], total - stats_after["missing_author_name"]),
        ("Thể loại sách (genres)", total - stats_before["missing_genres"], total - stats_after["missing_genres"]),
        ("Năm xuất bản (year)", total - stats_before["missing_year"], total - stats_after["missing_year"]),
        ("Mô tả sách (description)", total - stats_before["missing_desc"], total - stats_after["missing_desc"]),
        ("Số trang (num_pages)", total - stats_before["missing_pages"], total - stats_after["missing_pages"]),
        ("Nhà xuất bản (publisher)", total - stats_before["missing_publisher"], total - stats_after["missing_publisher"]),
        ("Ảnh bìa hợp lệ (ko nophoto)", total - stats_before["nophoto"], total - stats_after["nophoto"]),
        ("Mã ISBN", total - stats_before["missing_isbn"], total - stats_after["missing_isbn"]),
        ("Mã ISBN-13", total - stats_before["missing_isbn13"], total - stats_after["missing_isbn13"]),
    ]

    for label, b_val, a_val in metrics:
        b_pct = (b_val / total) * 100
        a_pct = (a_val / total) * 100
        diff_pct = a_pct - b_pct
        diff_str = f"(+{diff_pct:+.1f}%)" if diff_pct > 0 else ""
        print(f"{label:<28} | {b_val:>9,} ({b_pct:>5.1f}%) | {a_val:>9,} ({a_pct:>5.1f}%) {diff_str}", flush=True)

    print("=" * 75, flush=True)
    print("\nChi tiết các nguồn đã bổ sung:", flush=True)
    for k, v in enriched_counts.items():
        print(f"- {k}: {v:,} cuốn", flush=True)


if __name__ == "__main__":
    process_and_enrich()
