"""Xây bảng tra cứu ISBN -> (languages, cover_id) từ Open Library full dump và kiểm tra chất lượng dump.

Chạy một lần:
    python process/build_ol_lookup.py
    python process/build_ol_lookup.py --dump data/ol_dump_latest.txt.gz --out data/ol_isbn_lookup

Đầu ra: <out>/*.parquet cùng <out>/_quality.json (status = pass | fail).
Chỉ khi gate chất lượng đạt thì thư mục <out> mới được thay mới; nếu không, kết quả nằm ở <out>.failed.
"""
import os

# Worker spawn trên Windows import lại module này; hạn chế thread BLAS để tiết kiệm RAM.
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import gzip
import json
import logging
import multiprocessing as mp
import shutil
import sys
import time
import urllib.request
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

import orjson

sys.path.insert(0, str(Path(__file__).parent))
from book_enrichment import clean_isbn, is_valid_isbn10, is_valid_isbn13, isbn10_to_13, isbn13_to_10, isbn13_key  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / 'data'
DEFAULT_DUMP = DATA_DIR / 'ol_dump_latest.txt.gz'
DEFAULT_OUT = DATA_DIR / 'ol_isbn_lookup'
GOODREADS_BOOKS = DATA_DIR / 'goodreads_books.json'

EDITION_TYPE = b'/type/edition'
IGNORED_LANGUAGES = {'und', 'zxx'}
CHUNK_BYTES = 16 * 1024 * 1024
FLUSH_ROWS = 500_000

# Ngưỡng gate chất lượng. Tinh chỉnh sau khi đã xem số liệu thật trong _quality.json.
THRESHOLDS = {
    'max_bad_line_ratio': 0.0001,
    'max_json_error_ratio': 0.0001,
    'max_key_mismatch_ratio': 0.0001,
    'min_editions': 10_000_000,
    'min_works': 5_000_000,
    'min_authors': 2_000_000,
    'max_age_days': 548,                # last_modified lớn nhất phải nằm trong ~18 tháng
    'min_edition_isbn_ratio': 0.30,     # tỉ lệ edition có ISBN hợp lệ
    'min_edition_language_ratio': 0.50,
    'min_edition_cover_ratio': 0.20,
    'max_isbn_invalid_ratio': 0.10,     # ISBN sai checksum/độ dài trong tổng số giá trị ISBN
    'min_goodreads_match_ratio': 0.30,  # sách Goodreads có ISBN mà khớp được dump
    'min_goodreads_rescue_ratio': 0.20,  # sách Goodreads thiếu language (có ISBN) mà dump cứu được
}
GOODREADS_SAMPLE_LINES = 200_000
COVER_CHECK_SAMPLE = 50

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger('build_ol_lookup')

COLUMN_NAMES = ('isbn13', 'isbn10', 'languages', 'cover_id', 'last_modified', 'edition_key')


def row_schema():
    import pyarrow as pa
    return pa.schema([
        ('isbn13', pa.string()),
        ('isbn10', pa.string()),
        ('languages', pa.list_(pa.string())),
        ('cover_id', pa.int64()),
        ('last_modified', pa.string()),
        ('edition_key', pa.string()),
    ])


# ---------------------------------------------------------------------------
# Giai đoạn 1: stream dump (song song)
# ---------------------------------------------------------------------------

def parse_chunk(chunk):
    """Xử lý một khối byte gồm nhiều dòng TSV nguyên vẹn. Trả về (stats, cột dữ liệu edition)."""
    types = Counter()
    stats = Counter()
    max_modified = b''
    cols = {name: [] for name in COLUMN_NAMES}

    for line in chunk.split(b'\n'):
        if not line:
            continue
        parts = line.split(b'\t', 4)
        if len(parts) != 5:
            stats['bad_lines'] += 1
            continue
        record_type, key, _revision, modified, payload = parts
        types[record_type] += 1
        stats['lines'] += 1
        if modified > max_modified and len(modified) >= 10 and modified[:4].isdigit():
            max_modified = modified
        if record_type != EDITION_TYPE:
            continue

        stats['editions'] += 1
        try:
            doc = orjson.loads(payload)
        except orjson.JSONDecodeError:
            stats['json_errors'] += 1
            continue
        if not isinstance(doc, dict):
            stats['json_errors'] += 1
            continue
        if doc.get('key', '').encode() != key:
            stats['key_mismatch'] += 1

        # ISBN: gom từ cả isbn_10 và isbn_13, phân loại theo độ dài sau khi làm sạch
        keys = {}
        raw_values = []
        for field in ('isbn_13', 'isbn_10'):
            values = doc.get(field) or []
            if isinstance(values, list):
                raw_values.extend(v for v in values if isinstance(v, str))
        for raw in raw_values:
            code = clean_isbn(raw)
            stats['isbn_values'] += 1
            if is_valid_isbn13(code):
                keys.setdefault(code, None)
            elif is_valid_isbn10(code):
                keys.setdefault(isbn10_to_13(code), code)
            else:
                stats['isbn_invalid'] += 1

        languages = []
        for lang in doc.get('languages') or []:
            lang_key = lang.get('key') if isinstance(lang, dict) else None
            if isinstance(lang_key, str) and lang_key:
                code = lang_key.rsplit('/', 1)[-1]
                if code and code not in IGNORED_LANGUAGES and code not in languages:
                    languages.append(code)

        cover_id = None
        for cover in doc.get('covers') or []:
            if isinstance(cover, int) and not isinstance(cover, bool) and cover > 0:
                cover_id = cover
                break

        if raw_values:
            stats['editions_with_isbn_raw'] += 1
        if keys:
            stats['editions_with_valid_isbn'] += 1
            if languages:
                stats['editions_with_valid_isbn_language'] += 1
            if cover_id is not None:
                stats['editions_with_valid_isbn_cover'] += 1
        if languages:
            stats['editions_with_language'] += 1
        if cover_id is not None:
            stats['editions_with_cover'] += 1

        modified_text = modified.decode('ascii', 'replace')
        key_text = key.decode('utf-8', 'replace')
        for isbn13, isbn10 in keys.items():
            cols['isbn13'].append(isbn13)
            cols['isbn10'].append(isbn10 or isbn13_to_10(isbn13))
            cols['languages'].append(languages)
            cols['cover_id'].append(cover_id)
            cols['last_modified'].append(modified_text)
            cols['edition_key'].append(key_text)
            stats['rows'] += 1

    return dict(stats), dict(types), max_modified.decode('ascii', 'replace'), cols


def iter_chunks(stream, chunk_bytes=CHUNK_BYTES):
    """Đọc stream gzip theo khối, cắt tại ký tự xuống dòng cuối cùng."""
    carry = b''
    while True:
        data = stream.read(chunk_bytes)
        if not data:
            break
        data = carry + data
        cut = data.rfind(b'\n')
        if cut == -1:
            carry = data
            continue
        yield data[:cut + 1]
        carry = data[cut + 1:]
    if carry:
        yield carry


NUM_BUCKETS = 16


def isbn_bucket(isbn13):
    """Chia ISBN-13 thành NUM_BUCKETS nhóm đều nhau để khử trùng từng nhóm với RAM thấp."""
    return int(isbn13[8:12]) % NUM_BUCKETS


class RawWriter:
    """Ghi các dòng edition thô ra parquet, chia theo bucket ISBN."""

    def __init__(self, raw_dir):
        self.raw_dir = raw_dir
        self.buckets = [{name: [] for name in COLUMN_NAMES} for _ in range(NUM_BUCKETS)]
        self.rows = 0
        self.part = 0
        self.schema = row_schema()

    def add(self, cols):
        n = len(cols['isbn13'])
        if not n:
            return
        for i in range(n):
            bucket = self.buckets[isbn_bucket(cols['isbn13'][i])]
            for name in COLUMN_NAMES:
                bucket[name].append(cols[name][i])
        self.rows += n
        if self.rows >= FLUSH_ROWS:
            self.flush()

    def flush(self):
        if not self.rows:
            return
        import pyarrow as pa
        import pyarrow.parquet as pq
        for index, bucket in enumerate(self.buckets):
            if bucket['isbn13']:
                table = pa.table(bucket, schema=self.schema)
                pq.write_table(table, self.raw_dir / f'b{index:02d}-part-{self.part:05d}.parquet', compression='zstd')
        self.part += 1
        self.buckets = [{name: [] for name in COLUMN_NAMES} for _ in range(NUM_BUCKETS)]
        self.rows = 0


def stream_dump(dump_path, raw_dir, workers, limit_bytes=None):
    """Đọc toàn bộ dump (kiểm tra CRC gzip) và ghi các dòng edition ra parquet thô."""
    stats = Counter()
    types = Counter()
    max_modified = ''
    writer = RawWriter(raw_dir)
    gzip_ok = True
    gzip_error = None
    read_bytes = 0
    chunk_count = 0
    started = time.time()
    pending = deque()

    def drain_one():
        nonlocal max_modified
        s, t, m, cols = pending.popleft().get()
        stats.update(s)
        types.update({k.decode(): v for k, v in t.items()})
        if m > max_modified:
            max_modified = m
        writer.add(cols)

    pool = mp.Pool(workers)
    try:
        with gzip.open(dump_path, 'rb') as stream:
            for chunk in iter_chunks(stream):
                read_bytes += len(chunk)
                pending.append(pool.apply_async(parse_chunk, (chunk,)))
                while len(pending) >= workers * 2:
                    drain_one()
                chunk_count += 1
                if limit_bytes and read_bytes >= limit_bytes:
                    break
                if chunk_count % 50 == 0:
                    log.info(f"Đã đọc {read_bytes / 1e9:.1f} GB giải nén, {stats['lines']:,} dòng, "
                             f"{stats['editions']:,} edition, {time.time() - started:.0f}s")
        while pending:
            drain_one()
    except (EOFError, gzip.BadGzipFile, OSError, ValueError) as exc:
        gzip_ok = False
        gzip_error = f"{type(exc).__name__}: {exc}"
        log.error(f"Lỗi khi giải nén dump: {gzip_error}")
        pool.terminate()
        pending.clear()
    finally:
        pool.close()
        pool.join()
    writer.flush()
    return stats, types, max_modified, gzip_ok, gzip_error, read_bytes, time.time() - started


# ---------------------------------------------------------------------------
# Giai đoạn 2: khử trùng bằng DuckDB và đối chiếu Goodreads
# ---------------------------------------------------------------------------

def dedupe(con, raw_dir, out_dir):
    """Khử trùng theo isbn13 từng bucket một (RAM thấp), ghi mỗi bucket thành một file parquet.

    Mỗi isbn13 giữ language từ edition tốt nhất (có language, rồi last_modified mới nhất) và
    cover_id mới nhất trong số các edition có cover. Chỉ giữ dòng có language hoặc cover.
    Sau đó tạo view `dedup` trên thư mục kết quả để đối chiếu Goodreads.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    totals = Counter()
    for bucket in range(NUM_BUCKETS):
        raw_glob = str(raw_dir / f'b{bucket:02d}-*.parquet').replace('\\', '/')
        if not list(raw_dir.glob(f'b{bucket:02d}-*.parquet')):
            continue
        con.execute("DROP TABLE IF EXISTS bucket_dedup")
        con.execute(f"""
            CREATE TABLE bucket_dedup AS
            SELECT
                isbn13,
                any_value(isbn10) AS isbn10,
                arg_max(languages, concat(CASE WHEN len(languages) > 0 THEN '1' ELSE '0' END, last_modified, edition_key)) AS languages,
                arg_max(cover_id, last_modified) FILTER (WHERE cover_id IS NOT NULL) AS cover_id,
                count(*) AS edition_count
            FROM read_parquet('{raw_glob}')
            GROUP BY isbn13
        """)
        distinct, duplicated, kept, with_lang, with_cover = con.execute("""
            SELECT
                count(*),
                count(*) FILTER (WHERE edition_count > 1),
                count(*) FILTER (WHERE len(languages) > 0 OR cover_id IS NOT NULL),
                count(*) FILTER (WHERE len(languages) > 0),
                count(*) FILTER (WHERE cover_id IS NOT NULL)
            FROM bucket_dedup
        """).fetchone()
        totals['distinct_isbn13'] += distinct
        totals['isbn13_with_multiple_editions'] += duplicated
        totals['lookup_rows'] += kept
        totals['lookup_rows_with_language'] += with_lang
        totals['lookup_rows_with_cover'] += with_cover
        out_file = str(out_dir / f'part-{bucket:02d}.parquet').replace('\\', '/')
        con.execute(f"""
            COPY (
                SELECT isbn13, isbn10, languages, cover_id FROM bucket_dedup
                WHERE len(languages) > 0 OR cover_id IS NOT NULL
            ) TO '{out_file}' (FORMAT parquet, COMPRESSION zstd)
        """)
        log.info(f"Bucket {bucket:02d}: {distinct:,} ISBN-13 duy nhất, {kept:,} dòng tra cứu")
    con.execute("DROP TABLE IF EXISTS bucket_dedup")
    lookup_glob = str(out_dir / '*.parquet').replace('\\', '/')
    con.execute(f"CREATE VIEW dedup AS SELECT * FROM read_parquet('{lookup_glob}')")
    result = dict(totals)
    result['isbn13_duplicate_ratio'] = (
        totals['isbn13_with_multiple_editions'] / totals['distinct_isbn13'] if totals['distinct_isbn13'] else 0)
    return result


def goodreads_overlap(con, goodreads_path, sample_lines):
    """Đối chiếu bảng tra cứu (chỉ gồm ISBN có language hoặc cover) với các dòng đầu của goodreads_books.json."""
    if not goodreads_path.exists():
        return {'available': False}
    rows = []
    with open(goodreads_path, encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= sample_lines:
                break
            book = json.loads(line)
            key = isbn13_key(book.get('isbn'), book.get('isbn13'))
            language = (book.get('language_code') or '').strip()
            rows.append((key, language in ('', '--', 'Select...', 'und')))
    import pyarrow as pa
    gr_arrow = pa.table({
        'isbn13': pa.array([r[0] for r in rows], type=pa.string()),
        'lang_missing': pa.array([r[1] for r in rows], type=pa.bool_()),
    })
    con.register('gr_arrow', gr_arrow)
    con.execute("CREATE TABLE gr AS SELECT * FROM gr_arrow")
    result = con.execute("""
        SELECT
            count(*) AS books,
            count(*) FILTER (WHERE gr.isbn13 IS NOT NULL) AS with_isbn,
            count(*) FILTER (WHERE gr.isbn13 IS NOT NULL AND d.isbn13 IS NOT NULL) AS matched,
            count(*) FILTER (WHERE gr.lang_missing) AS lang_missing,
            count(*) FILTER (WHERE gr.lang_missing AND gr.isbn13 IS NOT NULL) AS lang_missing_with_isbn,
            count(*) FILTER (WHERE gr.lang_missing AND d.languages IS NOT NULL AND len(d.languages) > 0) AS lang_rescued,
            count(*) FILTER (WHERE gr.lang_missing AND gr.isbn13 IS NULL) AS lang_missing_no_isbn
        FROM gr LEFT JOIN dedup d ON gr.isbn13 = d.isbn13
    """).fetchone()
    books, with_isbn, matched, lang_missing, lang_missing_with_isbn, rescued, lang_missing_no_isbn = result
    return {
        'available': True,
        'sample_books': books,
        'books_with_isbn': with_isbn,
        'matched': matched,
        'match_ratio': matched / with_isbn if with_isbn else 0,
        'lang_missing': lang_missing,
        'lang_missing_with_isbn': lang_missing_with_isbn,
        'lang_rescued': rescued,
        'rescue_ratio': rescued / lang_missing_with_isbn if lang_missing_with_isbn else 0,
        'lang_missing_no_isbn_will_drop': lang_missing_no_isbn,
        'expected_dropped_ratio': (lang_missing - rescued) / books if books else 0,
    }


def check_cover_urls(con, sample_size):
    """Kiểm tra mẫu: HEAD một số URL cover. Không chặn gate."""
    try:
        ids = [r[0] for r in con.execute(
            f"SELECT cover_id FROM dedup WHERE cover_id IS NOT NULL ORDER BY hash(cover_id) LIMIT {sample_size}").fetchall()]
    except Exception as exc:
        return {'checked': 0, 'error': str(exc)}
    ok = 0
    errors = 0
    for cover_id in ids:
        url = f'https://covers.openlibrary.org/b/id/{cover_id}-L.jpg?default=false'
        try:
            request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'books-recommender-quality-check'})
            with urllib.request.urlopen(request, timeout=8) as response:
                if response.status == 200:
                    ok += 1
        except Exception:
            errors += 1
    return {'checked': len(ids), 'ok': ok, 'errors': errors, 'ok_ratio': ok / len(ids) if ids else None}


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def evaluate_gate(report, thresholds):
    failures = []
    if not report['gzip']['ok']:
        failures.append(f"gzip không toàn vẹn: {report['gzip']['error']}")
    if report.get('partial'):
        failures.append('chỉ đọc một phần dump (--limit-gb), không dùng được cho sản xuất')
    s = report['stats']
    lines = max(s.get('lines', 0) + s.get('bad_lines', 0), 1)
    editions = max(s.get('editions', 0), 1)
    types = report['type_counts']

    def check(name, value, limit, kind):
        ok = value <= limit if kind == 'max' else value >= limit
        if not ok:
            failures.append(f"{name}={value:.6g} {'>' if kind == 'max' else '<'} {limit:.6g}")

    check('bad_line_ratio', s.get('bad_lines', 0) / lines, thresholds['max_bad_line_ratio'], 'max')
    check('json_error_ratio', s.get('json_errors', 0) / editions, thresholds['max_json_error_ratio'], 'max')
    check('key_mismatch_ratio', s.get('key_mismatch', 0) / editions, thresholds['max_key_mismatch_ratio'], 'max')
    check('editions', types.get('/type/edition', 0), thresholds['min_editions'], 'min')
    check('works', types.get('/type/work', 0), thresholds['min_works'], 'min')
    check('authors', types.get('/type/author', 0), thresholds['min_authors'], 'min')

    max_modified = report.get('max_last_modified')
    if max_modified:
        try:
            newest = datetime.fromisoformat(max_modified).replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - newest).days
            report['dump_age_days'] = age
            check('dump_age_days', age, thresholds['max_age_days'], 'max')
        except ValueError:
            failures.append(f"last_modified không đọc được: {max_modified}")
    else:
        failures.append('không có last_modified')

    check('edition_isbn_ratio', s.get('editions_with_valid_isbn', 0) / editions, thresholds['min_edition_isbn_ratio'], 'min')
    check('edition_language_ratio', s.get('editions_with_language', 0) / editions, thresholds['min_edition_language_ratio'], 'min')
    check('edition_cover_ratio', s.get('editions_with_cover', 0) / editions, thresholds['min_edition_cover_ratio'], 'min')
    check('isbn_invalid_ratio', s.get('isbn_invalid', 0) / max(s.get('isbn_values', 0), 1), thresholds['max_isbn_invalid_ratio'], 'max')

    overlap = report.get('goodreads_overlap', {})
    if overlap.get('available'):
        check('goodreads_match_ratio', overlap['match_ratio'], thresholds['min_goodreads_match_ratio'], 'min')
        check('goodreads_rescue_ratio', overlap['rescue_ratio'], thresholds['min_goodreads_rescue_ratio'], 'min')
    else:
        log.warning('Không có goodreads_books.json: bỏ qua đối chiếu Goodreads')
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dump', type=Path, default=DEFAULT_DUMP)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--goodreads', type=Path, default=GOODREADS_BOOKS)
    parser.add_argument('--workers', type=int, default=max(2, min(4, (mp.cpu_count() or 4) - 2)),
                        help='Số worker parse JSON (mặc định thấp vì máy ít RAM trống)')
    parser.add_argument('--limit-gb', type=float, default=None, help='Chỉ đọc N GB giải nén đầu tiên (debug, gate luôn fail)')
    parser.add_argument('--skip-cover-check', action='store_true')
    parser.add_argument('--reuse-raw', action='store_true',
                        help='Dùng lại dữ liệu thô của lần chạy trước (<out>.building/raw) thay vì đọc lại dump')
    args = parser.parse_args()

    if not args.dump.exists():
        raise SystemExit(f"Không thấy dump: {args.dump}")

    out_dir = args.out
    building = out_dir.with_name(out_dir.name + '.building')
    failed_dir = out_dir.with_name(out_dir.name + '.failed')
    raw_dir = building / 'raw'
    lookup_dir = building / 'lookup'
    stage1_path = raw_dir / '_stage1.json'
    limit_bytes = int(args.limit_gb * 1e9) if args.limit_gb else None

    if args.reuse_raw and stage1_path.exists():
        log.info(f"Dùng lại dữ liệu thô tại {raw_dir}")
        stage1 = json.loads(stage1_path.read_text(encoding='utf-8'))
        stats, types = Counter(stage1['stats']), Counter(stage1['types'])
        max_modified, gzip_ok, gzip_error = stage1['max_modified'], stage1['gzip_ok'], stage1['gzip_error']
        read_bytes, elapsed = stage1['read_bytes'], stage1['elapsed']
        limit_bytes = stage1.get('limit_bytes')
        if failed_dir.exists():
            shutil.rmtree(failed_dir)
        if lookup_dir.exists():
            shutil.rmtree(lookup_dir)
    else:
        for path in (building, failed_dir):
            if path.exists():
                shutil.rmtree(path)
        raw_dir.mkdir(parents=True)
        log.info(f"Đọc dump {args.dump} ({args.dump.stat().st_size / 1e9:.1f} GB nén) bằng {args.workers} worker")
        stats, types, max_modified, gzip_ok, gzip_error, read_bytes, elapsed = stream_dump(
            args.dump, raw_dir, args.workers, limit_bytes)
        stage1_path.write_text(json.dumps({
            'stats': dict(stats), 'types': dict(types), 'max_modified': max_modified, 'gzip_ok': gzip_ok,
            'gzip_error': gzip_error, 'read_bytes': read_bytes, 'elapsed': elapsed, 'limit_bytes': limit_bytes,
        }), encoding='utf-8')

    report = {
        'dump': str(args.dump),
        'dump_size_bytes': args.dump.stat().st_size,
        'built_at': datetime.now(timezone.utc).isoformat(),
        'partial': bool(limit_bytes),
        'gzip': {'ok': gzip_ok, 'error': gzip_error, 'uncompressed_bytes_read': read_bytes},
        'stream_seconds': round(elapsed, 1),
        'stats': dict(stats),
        'type_counts': dict(types.most_common(30)),
        'max_last_modified': max_modified,
        'thresholds': THRESHOLDS,
    }

    if gzip_ok or limit_bytes:
        import duckdb
        con = duckdb.connect(str(building / 'work.duckdb'))
        con.execute(f"SET temp_directory='{(building / 'spill').as_posix()}'")
        con.execute("SET memory_limit='4GB'")
        con.execute("SET threads=4")
        report['lookup'] = dedupe(con, raw_dir, lookup_dir)
        report['goodreads_overlap'] = goodreads_overlap(con, args.goodreads, GOODREADS_SAMPLE_LINES)
        if not args.skip_cover_check:
            report['cover_url_check'] = check_cover_urls(con, COVER_CHECK_SAMPLE)
        con.close()

    failures = evaluate_gate(report, THRESHOLDS)
    report['failures'] = failures
    report['status'] = 'fail' if failures else 'pass'

    for name in ('work.duckdb', 'work.duckdb.wal', 'spill'):
        target = building / name
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()

    if failures:
        failed_dir.mkdir(parents=True, exist_ok=True)
        if lookup_dir.exists():
            for item in lookup_dir.iterdir():
                shutil.move(str(item), failed_dir / item.name)
        (failed_dir / '_quality.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        log.error(f"Dump KHÔNG đạt chất lượng: {failures}. Báo cáo: {failed_dir / '_quality.json'}")
        log.error(f"Dữ liệu thô giữ ở {raw_dir}; chỉnh ngưỡng rồi chạy lại với --reuse-raw.")
        sys.exit(1)

    (lookup_dir / '_quality.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.move(str(lookup_dir), str(out_dir))
    shutil.rmtree(building, ignore_errors=True)
    if failed_dir.exists():
        shutil.rmtree(failed_dir)
    log.info(f"Dump đạt chất lượng. Bảng tra cứu: {out_dir} ({report['lookup']['lookup_rows']:,} dòng)")


if __name__ == '__main__':
    mp.freeze_support()
    main()
