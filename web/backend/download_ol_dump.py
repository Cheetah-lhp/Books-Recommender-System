"""
Công cụ tải Open Library Data Dump (ol_dump_editions_latest.txt.gz)
- Hỗ trợ Resume (tải tiếp khi bị ngắt kết nối nhờ HTTP Range header)
- Kiểm tra dung lượng ổ đĩa trước khi tải
- Hiển thị tiến trình tải chi tiết
"""

import os
import sys
import shutil
import requests
import time

sys.stdout.reconfigure(encoding='utf-8')

# Open Library latest editions dump URL
DUMP_URL = "https://openlibrary.org/data/ol_dump_editions_latest.txt.gz"
DEST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEST_FILE = os.path.join(DEST_DIR, "ol_dump_editions_latest.txt.gz")
CHUNK_SIZE = 1024 * 1024  # 1 MB chunk


def check_disk_space(required_gb=15):
    total, used, free = shutil.disk_usage(DEST_DIR)
    free_gb = free / (1024 ** 3)
    print(f"Kiểm tra ổ đĩa: Trống {free_gb:.2f} GB (Yêu cầu tối thiểu {required_gb} GB)")
    if free_gb < required_gb:
        print(f"CẢNH BÁO: Dung lượng ổ đĩa trống ({free_gb:.2f} GB) có thể không đủ an toàn!")
        return False
    return True


def download_dump():
    print("=" * 60)
    print("DOWNLOAD OPEN LIBRARY EDITIONS DUMP")
    print(f"Nguồn: {DUMP_URL}")
    print(f"Đích lưu: {DEST_FILE}")
    print("=" * 60)

    if not check_disk_space(12):
        print("Dừng tải do cảnh báo dung lượng đĩa.")
        return

    # Kiểm tra kích thước file hiện tại nếu có để resume
    downloaded_bytes = 0
    if os.path.exists(DEST_FILE):
        downloaded_bytes = os.path.getsize(DEST_FILE)
        print(f"Phát hiện file đã tải một phần: {downloaded_bytes / (1024**2):.2f} MB")

    headers = {"User-Agent": "GoodreadsBRSEnricher/1.0 (Academic Recommender System)"}
    if downloaded_bytes > 0:
        headers["Range"] = f"bytes={downloaded_bytes}-"

    print("Đang kết nối đến Open Library server...")
    try:
        response = requests.get(DUMP_URL, headers=headers, stream=True, timeout=30)
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        return

    if response.status_code == 416:
        print("File đã được tải đầy đủ hoàn tất!")
        return
    elif response.status_code not in (200, 206):
        print(f"Server trả về mã trạng thái {response.status_code}: {response.text[:200]}")
        return

    content_length = response.headers.get("content-length")
    total_bytes = int(content_length) + downloaded_bytes if content_length else None
    mode = "ab" if downloaded_bytes > 0 and response.status_code == 206 else "wb"

    if mode == "wb":
        downloaded_bytes = 0

    print(f"Bắt đầu tải (Mode: {mode}, Tổng kích thước: {total_bytes / (1024**3):.2f} GB nếu có)...")
    start_time = time.time()
    last_print = time.time()

    with open(DEST_FILE, mode) as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                downloaded_bytes += len(chunk)

                if time.time() - last_print > 5:
                    last_print = time.time()
                    elapsed = time.time() - start_time
                    speed_mb = (downloaded_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = (downloaded_bytes / total_bytes * 100) if total_bytes else 0
                    print(f"   Đã tải: {downloaded_bytes / (1024**2):.1f} MB ({pct:.1f}%) - Tốc độ: {speed_mb:.2f} MB/s")

    print("\nTải Open Library Dump hoàn tất thành công!")
    print(f"Kích thước lưu: {os.path.getsize(DEST_FILE) / (1024**2):.2f} MB")


if __name__ == "__main__":
    download_dump()
