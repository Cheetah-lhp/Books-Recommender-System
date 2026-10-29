"""
Script Khử Trùng Lặp Tác Phẩm (Work-Level Deduplication):
- Quét qua tệp goodreads_books_enriched.json.gz (2.36 triệu cuốn)
- Mỗi tác phẩm (work_id), chọn đúng 1 ấn bản xuất sắc nhất dựa trên:
  + Lượt đánh giá (ratings_count)
  + Ảnh bìa hợp lệ (không phải nophoto)
  + Độ dài mô tả (description)
  + Đầy đủ ISBN, số trang, năm xuất bản
- Xuất ra 2 tệp kết quả:
  1. goodreads_books_deduplicated.json.gz (Toàn bộ các tác phẩm độc nhất)
  2. goodreads_books_dedup_1m.json.gz (Top 1.000.000 tác phẩm chất lượng nhất - tối ưu chuẩn cho Aiven 8 GB)
- Thống kê chi tiết số lượng và dung lượng ước tính trên PostgreSQL
"""

import gzip
import json
import os
import sys
import time
import psutil

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
INPUT_PATH = os.path.join(BASE_DIR, "goodreads_books_enriched.json.gz")
OUTPUT_ALL_DEDUP = os.path.join(BASE_DIR, "goodreads_books_deduplicated.json.gz")
OUTPUT_1M = os.path.join(BASE_DIR, "goodreads_books_dedup_1m.json.gz")

# Dung lượng trung bình 1 cuốn sách trong PostgreSQL Aiven (đo đạc thực nghiệm)
BYTES_PER_BOOK_PG = 6078.5  # ~5.94 KB


def get_ram_usage_mb():
    p = psutil.Process(os.getpid())
    return p.memory_info().rss / (1024 * 1024)


def calc_quality_score(book):
    try:
        ratings_cnt = int(book.get("ratings_count") or 0)
    except Exception:
        ratings_cnt = 0

    img = book.get("image_url", "")
    has_valid_cover = 1 if img and "nophoto" not in img else 0

    desc = book.get("description") or ""
    desc_len = min(len(desc), 1500)

    has_isbn = 1 if (book.get("isbn13") or book.get("isbn")) else 0
    has_pages = 1 if book.get("num_pages") else 0
    has_year = 1 if book.get("publication_year") else 0
    has_pub = 1 if book.get("publisher") else 0

    # Trọng số tổng hợp
    score = (
        ratings_cnt * 10
        + has_valid_cover * 1000
        + has_isbn * 500
        + has_pages * 200
        + has_year * 200
        + has_pub * 100
        + desc_len
    )
    return score


def run_deduplication():
    if not os.path.exists(INPUT_PATH):
        print(f"Lỗi: Không tìm thấy tệp {INPUT_PATH}!")
        return

    print("=" * 70)
    print("BẮT ĐẦU KHỬ TRÙNG LẶP TÁC PHẨM (WORK-LEVEL DEDUPLICATION)")
    print(f"Nguồn dữ liệu: {INPUT_PATH}")
    print("=" * 70, flush=True)

    start_t = time.time()

    # Pass 1: Quét tìm ấn bản tốt nhất cho mỗi work_id
    print("[1/3] Pass 1: Đánh giá điểm chất lượng và chọn ấn bản đại diện cho mỗi tác phẩm...", flush=True)
    best_per_work = {}  # work_key -> (score, book_id)
    total_scanned = 0

    with gzip.open(INPUT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            total_scanned += 1
            b = json.loads(line)
            b_id = str(b.get("book_id"))
            w_id = str(b.get("work_id") or "")

            # Nếu có work_id thì nhóm theo work_id, nếu không có thì giữ theo book_id
            group_key = w_id if (w_id and w_id != "None" and w_id != "") else f"book_{b_id}"
            score = calc_quality_score(b)

            if group_key not in best_per_work or score > best_per_work[group_key][0]:
                best_per_work[group_key] = (score, b_id)

            if total_scanned % 500000 == 0:
                print(f"   Đã quét {total_scanned:,}/2,360,655 cuốn ({time.time() - start_t:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)...", flush=True)

    total_unique_works = len(best_per_work)
    print(f"\n -> Quét xong {total_scanned:,} cuốn trong {time.time() - start_t:.1f}s!", flush=True)
    print(f" -> Tổng số tác phẩm độc nhất: {total_unique_works:,} tác phẩm.")
    print(f" -> Đã loại bỏ: {total_scanned - total_unique_works:,} ấn bản trùng lặp ({(total_scanned - total_unique_works)/total_scanned*100:.1f}%).\n", flush=True)

    # Sắp xếp các tác phẩm theo điểm chất lượng từ cao xuống thấp
    print("[2/3] Sắp xếp xếp hạng chất lượng các tác phẩm để chuẩn bị phân phối...", flush=True)
    sorted_items = sorted(best_per_work.values(), key=lambda x: x[0], reverse=True)

    # Tập hợp các book_id của toàn bộ tác phẩm độc nhất
    all_dedup_book_ids = set(b_id for score, b_id in sorted_items)

    # Tập hợp Top 1.000.000 tác phẩm xuất sắc nhất
    top_1m_book_ids = set(b_id for score, b_id in sorted_items[:1000000])

    print(f" -> Đã chọn {len(all_dedup_book_ids):,} tác phẩm cho tệp Toàn bộ.")
    print(f" -> Đã chọn {len(top_1m_book_ids):,} tác phẩm cho tệp Top 1 Triệu Cuốn.\n", flush=True)

    # Pass 2: Trích xuất và ghi ra 2 tệp nén
    print("[3/3] Pass 2: Trích xuất các ấn bản được chọn và xuất ra tệp nén...", flush=True)
    t2_start = time.time()

    tmp_all = OUTPUT_ALL_DEDUP + ".tmp"
    tmp_1m = OUTPUT_1M + ".tmp"

    count_all = 0
    count_1m = 0

    with gzip.open(INPUT_PATH, "rt", encoding="utf-8") as f_in, \
         gzip.open(tmp_all, "wt", compresslevel=1, encoding="utf-8") as f_all, \
         gzip.open(tmp_1m, "wt", compresslevel=1, encoding="utf-8") as f_1m:

        for line in f_in:
            b = json.loads(line)
            b_id = str(b.get("book_id"))

            if b_id in all_dedup_book_ids:
                f_all.write(json.dumps(b, ensure_ascii=False) + "\n")
                count_all += 1

                if b_id in top_1m_book_ids:
                    f_1m.write(json.dumps(b, ensure_ascii=False) + "\n")
                    count_1m += 1

            if count_all % 200000 == 0 and count_all > 0:
                print(f"   Đã xuất {count_all:,} tác phẩm ({time.time() - t2_start:.1f}s, RAM: {get_ram_usage_mb():.1f} MB)...", flush=True)

    # Đổi tên file tạm thành file chính
    if os.path.exists(OUTPUT_ALL_DEDUP): os.remove(OUTPUT_ALL_DEDUP)
    os.rename(tmp_all, OUTPUT_ALL_DEDUP)

    if os.path.exists(OUTPUT_1M): os.remove(OUTPUT_1M)
    os.rename(tmp_1m, OUTPUT_1M)

    total_time = time.time() - start_t
    print("\n" + "=" * 70)
    print(f"HOÀN TẤT KHỬ TRÙNG LẶP ({total_time:.1f} giây, ~{total_time/60:.2f} phút)!")
    print("=" * 70, flush=True)

    size_all_mb = os.path.getsize(OUTPUT_ALL_DEDUP) / (1024 * 1024)
    size_1m_mb = os.path.getsize(OUTPUT_1M) / (1024 * 1024)

    # Tính toán dung lượng lưu trữ trên PostgreSQL Aiven
    est_pg_all_gb = (count_all * BYTES_PER_BOOK_PG) / (1024 ** 3)
    est_pg_1m_gb = (count_1m * BYTES_PER_BOOK_PG) / (1024 ** 3)

    print("\nBÁO CÁO THỐNG KÊ & DUNG LƯỢNG TRÊN AIVEN POSTGRESQL (8 GB LIMIT):")
    print("-" * 75)
    print(f"{'MỤC DỮ LIỆU':<32} | {'SỐ CUỐN SÁCH':<15} | {'FILE NÉN GZ':<12} | {'DUNG LƯỢNG POSTGRESQL'}")
    print("-" * 75)
    print(f"{'Dữ liệu gốc ban đầu':<32} | {'2,360,655':<15} | {'2,572 MB':<12} | ~13.36 GB (QUÁ TẢI 8GB)")
    print(f"{'Tất cả tác phẩm độc nhất':<32} | {f'{count_all:,}':<15} | {f'{size_all_mb:.1f} MB':<12} | ~{est_pg_all_gb:.2f} GB (Sát nút 8GB)")
    print(f"{'Top 1 Triệu Tác Phẩm Tốt Nhất':<32} | {f'{count_1m:,}':<15} | {f'{size_1m_mb:.1f} MB':<12} | ~{est_pg_1m_gb:.2f} GB (AN TOÀN TRÊN AIVEN)")
    print("-" * 75)

    print("\nChi tiết các tệp đã tạo:")
    print(f"1. Toàn bộ tác phẩm độc nhất: {OUTPUT_ALL_DEDUP} ({size_all_mb:.1f} MB)")
    print(f"2. Top 1.000.000 tác phẩm tốt nhất: {OUTPUT_1M} ({size_1m_mb:.1f} MB)")


if __name__ == "__main__":
    run_deduplication()
