"""
Script làm giàu dữ liệu từ Open Library Dump: ol_dump_editions_latest.txt.gz
- Đọc trực tiếp luồng gzip (streaming), không giải nén bung ra ổ đĩa
- Khớp theo ISBN/ISBN-13 đối với các sách còn khuyết thông tin
- Bổ sung pages, publisher, publish_date, description, covers
"""

import gzip
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OL_DUMP_PATH = os.path.join(BASE_DIR, "ol_dump_editions_latest.txt.gz")
ENRICHED_PATH = os.path.join(BASE_DIR, "goodreads_books_enriched.json.gz")
FINAL_OUTPUT_PATH = os.path.join(BASE_DIR, "goodreads_books_enriched_v2.json.gz")


def extract_ol_metadata(ol_data):
    """Trích xuất các trường thông tin chuẩn từ bản ghi Open Library Edition"""
    isbns = set()
    for isbn in ol_data.get("isbn_10", []):
        if isbn: isbns.add(str(isbn).strip().upper())
    for isbn in ol_data.get("isbn_13", []):
        if isbn: isbns.add(str(isbn).strip().upper())

    pages = str(ol_data.get("number_of_pages", "")).strip()
    publishers = ol_data.get("publishers", [])
    publisher = publishers[0] if isinstance(publishers, list) and publishers else ""
    publish_date = str(ol_data.get("publish_date", "")).strip()

    # Mô tả trong OL có thể là string hoặc {"value": "..."}
    desc_obj = ol_data.get("description", "")
    description = desc_obj.get("value", "") if isinstance(desc_obj, dict) else str(desc_obj)

    covers = ol_data.get("covers", [])
    cover_id = str(covers[0]) if covers and covers[0] > 0 else ""
    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else ""

    return {
        "isbns": isbns,
        "pages": pages,
        "publisher": publisher,
        "publish_date": publish_date,
        "description": description.strip(),
        "cover_url": cover_url
    }


def stream_enrich_from_ol():
    if not os.path.exists(OL_DUMP_PATH):
        print(f"Chưa tìm thấy tệp dump Open Library tại: {OL_DUMP_PATH}")
        print("Vui lòng chạy 'python brs_api/download_ol_dump.py' trước để tải tệp về.")
        return

    if not os.path.exists(ENRICHED_PATH):
        print(f"Chưa tìm thấy tệp {ENRICHED_PATH}. Vui lòng chạy 'python brs_api/enrich_full_dump.py' trước.")
        return

    print("=" * 65)
    print("ENRICH FROM OPEN LIBRARY DUMP (STREAMING)")
    print("=" * 65)

    # 1. Quét thu thập tập hợp ISBN của những cuốn sách còn khuyết thông tin
    print("[1/3] Đang thu thập các cuốn sách còn thiếu trường từ goodreads_books_enriched.json.gz...")
    start_t = time.time()
    needed_isbns = {}  # isbn -> list of book_id
    total_books = 0

    with gzip.open(ENRICHED_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            total_books += 1
            b = json.loads(line)
            # Nếu còn thiếu pages, publisher, year, description hoặc nophoto
            is_nophoto = not b.get("image_url") or "nophoto" in b.get("image_url")
            needs_enrich = (not b.get("num_pages") or not b.get("publisher") or 
                            not b.get("publication_year") or not b.get("description") or is_nophoto)
            if needs_enrich:
                isbn = b.get("isbn", "").strip().upper()
                isbn13 = b.get("isbn13", "").strip().upper()
                b_id = b.get("book_id")
                if isbn:
                    needed_isbns.setdefault(isbn, []).append(b_id)
                if isbn13:
                    needed_isbns.setdefault(isbn13, []).append(b_id)

    print(f" -> Tổng cộng {total_books:,} sách, có {len(needed_isbns):,} mã ISBN cần bổ sung thông tin.")

    # 2. Đọc luồng Open Library Dump
    print("[2/3] Quét luồng Open Library Editions Dump...")
    ol_matches = {}  # book_id -> dict of enriched fields
    ol_line_count = 0
    matched_count = 0

    with gzip.open(OL_DUMP_PATH, "rt", encoding="utf-8") as f_ol:
        for line in f_ol:
            ol_line_count += 1
            if ol_line_count % 500000 == 0:
                print(f"   Đã quét {ol_line_count:,} bản ghi Open Library (Khớp {matched_count:,} cuốn)...")

            # TSV format: type \t key \t revision \t last_modified \t JSON
            parts = line.split("\t", 4)
            if len(parts) < 5:
                continue

            try:
                ol_data = json.loads(parts[4])
            except Exception:
                continue

            extracted = extract_ol_metadata(ol_data)
            common_isbns = extracted["isbns"].intersection(needed_isbns.keys())
            if common_isbns:
                for match_isbn in common_isbns:
                    for b_id in needed_isbns[match_isbn]:
                        if b_id not in ol_matches:
                            ol_matches[b_id] = extracted
                            matched_count += 1

    print(f" -> Đã khớp thành công {len(ol_matches):,} cuốn sách từ Open Library Dump!")

    # 3. Ghi ra tệp enriched mới
    print("[3/3] Xuất bản file enriched hoàn chỉnh...")
    with gzip.open(ENRICHED_PATH, "rt", encoding="utf-8") as f_in, \
         gzip.open(FINAL_OUTPUT_PATH, "wt", encoding="utf-8") as f_out:
        for line in f_in:
            b = json.loads(line)
            b_id = b.get("book_id")
            if b_id in ol_matches:
                ol_info = ol_matches[b_id]
                if not b.get("num_pages") and ol_info["pages"]:
                    b["num_pages"] = ol_info["pages"]
                if not b.get("publisher") and ol_info["publisher"]:
                    b["publisher"] = ol_info["publisher"]
                if not b.get("description") and ol_info["description"]:
                    b["description"] = ol_info["description"]
                if (not b.get("image_url") or "nophoto" in b.get("image_url")) and ol_info["cover_url"]:
                    b["image_url"] = ol_info["cover_url"]
            f_out.write(json.dumps(b, ensure_ascii=False) + "\n")

    print(f"Hoàn tất Giai đoạn 2! Tệp lưu tại: {FINAL_OUTPUT_PATH}")


if __name__ == "__main__":
    stream_enrich_from_ol()
