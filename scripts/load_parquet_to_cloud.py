"""
Nap du lieu parquet tu samples_data/ va full_data/ len MySQL cloud (Aiven).

- Moi bang duoc tao voi tien to: samples_<ten> hoac full_<ten> (khong dung bang cua web).
- Bang da co du so dong (COUNT >= so dong parquet) thi bo qua, nen chay lai an toan.
- Bang co khoa chinh: nap tung file parquet voi INSERT IGNORE + trang thai resume theo file.
- Bang khong co khoa chinh: neu nap do thi se TRUNCATE roi nap lai (bang nay do script tao ra).
- Thu muc nguon chi duoc doc, khong xoa hay sua.

Vi du:
  python scripts/load_parquet_to_cloud.py --source samples --dry-run
  python scripts/load_parquet_to_cloud.py --source all
  python scripts/load_parquet_to_cloud.py --source full --tables books,interactions --workers 3
"""

import argparse
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

SOURCE_DIRS = {
    "samples": ROOT / "samples_data",
    "full": ROOT / "full_data_clean" if (ROOT / "full_data_clean").exists() else ROOT / "full_data",
}

DEFAULT_STATE_FILE = ROOT / "checkpoints" / "cloud_load_state.json"

# Khoa chinh cho tung bang. None = khong co khoa (bang co dong trung hoan toan).
TABLE_KEYS = {
    "books": ["book_id"],
    "authors": ["author_id"],
    "works": ["work_id"],
    "series": ["series_id"],
    "reviews": ["review_id"],
    "interactions": ["book_id", "user_id"],
    "genres": ["book_id", "genres"],
    "book_series_map": ["book_id", "series_id"],
    "book_authors_map": None,
}

# Thu tu uu tien nap bang nho/catalog truoc, hai bang rat lon nap sau cung.
TABLE_PRIORITY = {
    "book_series_map": 1,
    "genres": 2,
    "book_authors_map": 3,
    "authors": 4,
    "series": 5,
    "works": 6,
    "books": 7,
    "reviews": 8,
    "interactions": 9,
}

# Batch size toi uu theo do rong ban ghi (max_stmt_length = 8 MiB van gioi han an toan < 64 MiB).
TABLE_BATCH_ROWS = {
    "interactions": 30000,
    "genres": 20000,
    "book_series_map": 20000,
    "book_authors_map": 15000,
    "authors": 5000,
    "series": 3000,
    "works": 3000,
    "books": 2000,
    "reviews": 2000,
}

DEFAULT_BATCH_ROWS = 2000
MAX_STMT_LENGTH = 8 * 1024 * 1024
KEY_STRING_LENGTH = 255
MAX_RETRIES = 5


def _db_settings():
    host = os.getenv("DB_HOST", "").strip()
    if not host or host == "mysql":
        sys.exit("Loi: DB_HOST chua duoc cau hinh cho MySQL cloud trong .env")
    ssl_mode = os.getenv("DB_SSL_MODE", "").strip().upper()
    ssl_ca = os.getenv("DB_SSL_CA", "").strip()
    ssl_args = None
    if ssl_mode not in ("", "DISABLED", "DISABLE", "OFF"):
        ssl_args = {"ca": ssl_ca, "check_hostname": ssl_mode == "VERIFY_IDENTITY"} if ssl_ca else {}
    return {
        "host": host,
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME") or os.getenv("WEB_DB_NAME") or "defaultdb",
        "ssl": ssl_args,
    }


def connect(settings, autocommit=False):
    kwargs = dict(
        host=settings["host"],
        port=settings["port"],
        user=settings["user"],
        password=settings["password"],
        database=settings["database"],
        charset="utf8mb4",
        autocommit=autocommit,
        connect_timeout=30,
        read_timeout=600,
        write_timeout=600,
    )
    if settings["ssl"] is not None:
        kwargs["ssl"] = settings["ssl"]
    return pymysql.connect(**kwargs)


def discover_tables(source_dir):
    """Tra ve {ten_bang: thu_muc} theo thu tu uu tien nap bang nho truoc."""
    tables = {}
    if not source_dir.exists():
        return tables
    dirs = [c for c in source_dir.iterdir() if c.is_dir() and any(c.rglob("*.parquet"))]
    dirs.sort(key=lambda d: (TABLE_PRIORITY.get(d.name, 99), d.name))
    for child in dirs:
        tables[child.name] = child
    return tables


def parquet_files(table_dir):
    return sorted(table_dir.rglob("*.parquet"))


def parquet_size_bytes(table_dir):
    return sum(p.stat().st_size for p in parquet_files(table_dir))


def mysql_column_type(arrow_type, is_key):
    if pa.types.is_integer(arrow_type):
        return "BIGINT"
    if pa.types.is_floating(arrow_type):
        return "DOUBLE"
    if pa.types.is_boolean(arrow_type):
        return "TINYINT(1)"
    if pa.types.is_timestamp(arrow_type):
        return "DATETIME"
    if is_key and (pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type)):
        return f"VARCHAR({KEY_STRING_LENGTH})"
    return "LONGTEXT"


def to_mysql_value(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, datetime):
        # DATETIME trong MySQL khong luu mui gio: doi ve UTC roi bo tzinfo
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return json.dumps(value, default=str, ensure_ascii=False)


def build_create_sql(prefixed_name, schema, key_cols):
    column_defs = []
    for field in schema:
        col_type = mysql_column_type(field.type, field.name in (key_cols or []))
        nullable = "NOT NULL" if key_cols and field.name in key_cols else "NULL"
        column_defs.append(f"`{field.name}` {col_type} {nullable}")
    if key_cols:
        key_sql = ", ".join(f"`{c}`" for c in key_cols)
        column_defs.append(f"PRIMARY KEY ({key_sql})")
    else:
        # Aiven bat sql_require_primary_key: bang khong co khoa can them khoa dong.
        column_defs.insert(0, "`_row_id` BIGINT NOT NULL AUTO_INCREMENT")
        column_defs.append("PRIMARY KEY (`_row_id`)")
    body = ",\n    ".join(column_defs)
    return (
        f"CREATE TABLE IF NOT EXISTS `{prefixed_name}` (\n    {body}\n)"
        " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    )


def resolve_key_cols(table_name, schema):
    key_cols = TABLE_KEYS.get(table_name)
    if key_cols is None:
        return None
    names = set(schema.names)
    missing = [c for c in key_cols if c not in names]
    if missing:
        print(f"  [canh bao] Thieu cot khoa {missing}, bang se khong co khoa chinh.")
        return None
    return key_cols


def count_rows_mysql(cur, prefixed_name):
    cur.execute(f"SELECT COUNT(*) FROM `{prefixed_name}`")
    return int(cur.fetchone()[0])


def table_exists(cur, prefixed_name):
    cur.execute("SHOW TABLES LIKE %s", (prefixed_name,))
    return cur.fetchone() is not None


class StateStore:
    """Luu trang thai cac file parquet da commit thanh cong de resume an toan."""

    def __init__(self, path: Path, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self._lock = threading.Lock()
        self.data = {}
        if enabled and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def _save_unlocked(self):
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get_table(self, key: str) -> dict:
        with self._lock:
            return dict(self.data.get(key, {}))

    def is_file_done(self, key: str, rel_file: str, size: int) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            files = self.data.get(key, {}).get("done_files", {})
            return files.get(rel_file) == size

    def mark_file_done(self, key: str, rel_file: str, size: int):
        if not self.enabled:
            return
        with self._lock:
            entry = self.data.setdefault(key, {"done_files": {}, "completed": False})
            entry.setdefault("done_files", {})[rel_file] = size
            self._save_unlocked()

    def mark_table_completed(self, key: str, final_rows: int):
        if not self.enabled:
            return
        with self._lock:
            entry = self.data.setdefault(key, {"done_files": {}, "completed": False})
            entry["completed"] = True
            entry["final_rows"] = final_rows
            self._save_unlocked()

    def reset_table(self, key: str):
        if not self.enabled:
            return
        with self._lock:
            if key in self.data:
                del self.data[key]
                self._save_unlocked()


def _prepare_batch_rows(batch, json_cols):
    columns_data = []
    for i in range(batch.num_columns):
        values = batch.column(i).to_pylist()
        if i in json_cols:
            values = [None if v is None else json.dumps(v, default=str, ensure_ascii=False) for v in values]
        else:
            values = [to_mysql_value(v) for v in values]
        columns_data.append(values)
    return list(zip(*columns_data))


def _insert_batch_with_retry(settings, conn_holder, insert_sql, rows):
    for attempt in range(1, MAX_RETRIES + 1):
        conn = conn_holder[0]
        try:
            with conn.cursor() as cur:
                cur.max_stmt_length = MAX_STMT_LENGTH
                cur.executemany(insert_sql, rows)
            conn.commit()
            return
        except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as exc:
            try:
                conn.close()
            except Exception:
                pass
            if attempt == MAX_RETRIES:
                raise
            wait_s = min(30, 2 ** attempt)
            print(f"    [thu lai {attempt}/{MAX_RETRIES}] Mat ket noi tam thoi ({exc}), cho {wait_s}s...")
            time.sleep(wait_s)
            conn_holder[0] = connect(settings, autocommit=False)


def _process_one_file(
    settings,
    prefixed,
    table_dir,
    file_path,
    columns,
    json_cols,
    insert_sql,
    batch_rows,
    state: StateStore,
    progress_counter: list,
    progress_lock: threading.Lock,
    expected: int,
    t0: float,
):
    rel_name = str(file_path.relative_to(table_dir))
    fsize = file_path.stat().st_size
    pf = pq.ParquetFile(file_path)
    file_rows = pf.metadata.num_rows

    conn_holder = [connect(settings, autocommit=False)]
    try:
        for batch in pf.iter_batches(batch_size=batch_rows, columns=columns):
            rows = _prepare_batch_rows(batch, json_cols)
            if rows:
                _insert_batch_with_retry(settings, conn_holder, insert_sql, rows)
            with progress_lock:
                progress_counter[0] += batch.num_rows
                progress_counter[2] += batch.num_rows
                done = progress_counter[0]
                last_log = progress_counter[1]
                now = time.time()
                if done == expected or now - last_log >= 15.0:
                    elapsed = max(now - t0, 0.001)
                    progress_counter[1] = now
                    pct = (100.0 * done / expected) if expected else 100.0
                    print(
                        f"    [{prefixed}] {done:,}/{expected:,} ({pct:.1f}%) "
                        f"| toc do ~{int(progress_counter[2] / elapsed):,} dong/s",
                        flush=True,
                    )
        state.mark_file_done(prefixed, rel_name, fsize)
        return file_rows
    finally:
        try:
            conn_holder[0].close()
        except Exception:
            pass


def target_table_name(source_name: str, table_name: str, full_prefix: str = "") -> str:
    if source_name == "full":
        return f"{full_prefix}{table_name}" if full_prefix else table_name
    return f"{source_name}_{table_name}"


def load_table(
    conn,
    settings,
    source_name,
    table_name,
    table_dir,
    workers: int,
    state: StateStore,
    full_prefix: str = "",
):
    prefixed = target_table_name(source_name, table_name, full_prefix=full_prefix)
    files = parquet_files(table_dir)
    dataset = ds.dataset(str(table_dir), format="parquet")
    expected = dataset.count_rows()
    schema = dataset.schema
    key_cols = resolve_key_cols(table_name, schema)
    batch_rows = TABLE_BATCH_ROWS.get(table_name, DEFAULT_BATCH_ROWS)

    table_state = state.get_table(prefixed)
    with conn.cursor() as cur:
        exists = table_exists(cur, prefixed)
        if not exists:
            state.reset_table(prefixed)
            table_state = {}
            cur.execute(build_create_sql(prefixed, schema, key_cols))
            conn.commit()
            print(f"  [tao bang] `{prefixed}` (khoa: {key_cols or 'khong co'})", flush=True)
        else:
            if table_state.get("completed"):
                print(
                    f"  [bo qua] `{prefixed}` da hoan tat truoc do "
                    f"({table_state.get('final_rows', expected):,}/{expected:,} dong).",
                    flush=True,
                )
                return
            if key_cols is None:
                current = count_rows_mysql(cur, prefixed)
                if current >= expected:
                    state.mark_table_completed(prefixed, current)
                    print(f"  [bo qua] `{prefixed}` da du {current:,}/{expected:,} dong.", flush=True)
                    return
                if current > 0:
                    print(f"  [nap lai] `{prefixed}` nap do ({current:,}/{expected:,}), TRUNCATE roi nap lai.", flush=True)
                    cur.execute(f"TRUNCATE TABLE `{prefixed}`")
                    conn.commit()
                state.reset_table(prefixed)
            elif not table_state.get("done_files"):
                # Chua co file state (vd bang samples_* tao tu ban cu): dem so dong xem da du chua.
                current = count_rows_mysql(cur, prefixed)
                if current >= expected:
                    state.mark_table_completed(prefixed, current)
                    print(f"  [bo qua] `{prefixed}` da du {current:,}/{expected:,} dong.", flush=True)
                    return

    pending_files = []
    skipped_rows = 0
    for f in files:
        rel = str(f.relative_to(table_dir))
        fsize = f.stat().st_size
        if key_cols is not None and state.is_file_done(prefixed, rel, fsize):
            skipped_rows += pq.read_metadata(f).num_rows
        else:
            pending_files.append(f)

    if not pending_files:
        with conn.cursor() as cur:
            final = count_rows_mysql(cur, prefixed)
        state.mark_table_completed(prefixed, final)
        print(f"  [xong] `{prefixed}`: {final:,} dong (khong con file cho).", flush=True)
        return

    columns = schema.names
    col_sql = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    verb = "INSERT IGNORE" if key_cols else "INSERT"
    insert_sql = f"{verb} INTO `{prefixed}` ({col_sql}) VALUES ({placeholders})"

    json_cols = {
        i for i, field in enumerate(schema)
        if pa.types.is_list(field.type) or pa.types.is_struct(field.type) or pa.types.is_map(field.type)
    }

    eff_workers = 1 if (key_cols is None or len(pending_files) == 1) else max(1, min(workers, len(pending_files)))
    print(
        f"  [nap] `{prefixed}`: {expected:,} dong ({len(pending_files)}/{len(files)} file con lai, "
        f"da bo qua {skipped_rows:,}, batch={batch_rows:,}, workers={eff_workers}) ...",
        flush=True,
    )

    t0 = time.time()
    progress_counter = [skipped_rows, t0, 0]  # [total_done, last_log_ts, session_rows]
    progress_lock = threading.Lock()

    if eff_workers == 1:
        for f in pending_files:
            _process_one_file(
                settings, prefixed, table_dir, f, columns, json_cols,
                insert_sql, batch_rows, state, progress_counter, progress_lock, expected, t0
            )
    else:
        with ThreadPoolExecutor(max_workers=eff_workers) as pool:
            futures = [
                pool.submit(
                    _process_one_file,
                    settings, prefixed, table_dir, f, columns, json_cols,
                    insert_sql, batch_rows, state, progress_counter, progress_lock, expected, t0
                )
                for f in pending_files
            ]
            for fut in as_completed(futures):
                fut.result()

    with conn.cursor() as cur:
        final = count_rows_mysql(cur, prefixed)
    state.mark_table_completed(prefixed, final)
    elapsed = time.time() - t0
    if final == expected:
        print(f"  [xong] `{prefixed}`: {final:,} dong, khop parquet ({elapsed:.1f}s).", flush=True)
    else:
        print(
            f"  [xong] `{prefixed}`: {final:,} dong trong MySQL, parquet {expected:,} dong ({elapsed:.1f}s) "
            "(chenh lech do dong trung khoa trong nguon da duoc bo qua).",
            flush=True,
        )


def run(args):
    source_dirs = dict(SOURCE_DIRS)
    if args.full_dir:
        p = Path(args.full_dir)
        source_dirs["full"] = p if p.is_absolute() else (ROOT / p)
    sources = ["samples", "full"] if args.source == "all" else [args.source]
    wanted = set(t.strip() for t in args.tables.split(",") if t.strip()) if args.tables else None

    plan = []
    for source_name in sources:
        source_dir = source_dirs[source_name]
        tables = discover_tables(source_dir)
        if not tables:
            print(f"[canh bao] Khong tim thay du lieu parquet trong {source_dir.name}/, bo qua.")
            continue
        for table_name, table_dir in tables.items():
            if wanted and table_name not in wanted:
                continue
            plan.append((source_name, table_name, table_dir))

    if not plan:
        print("Khong co bang nao de nap.")
        return 0

    if args.dry_run:
        total_bytes = 0
        for source_name, table_name, table_dir in plan:
            dataset = ds.dataset(str(table_dir), format="parquet")
            size = parquet_size_bytes(table_dir)
            total_bytes += size
            dest_name = target_table_name(source_name, table_name, full_prefix=args.full_prefix)
            print(
                f"{dest_name}: {dataset.count_rows():,} dong, "
                f"parquet {size / 1024 / 1024:,.1f} MB, khoa: {resolve_key_cols(table_name, dataset.schema) or 'khong co'}"
            )
        print(f"Tong parquet: {total_bytes / 1024 / 1024:,.1f} MB (dung luong tren MySQL thuong lon hon).")
        print("Dry-run: khong ket noi MySQL, khong ghi gi.")
        return 0

    settings = _db_settings()
    state = StateStore(Path(args.state_file), enabled=not args.no_resume_state)
    print(
        f"Ket noi MySQL {settings['host']}:{settings['port']}/{settings['database']} "
        f"(SSL: {'co' if settings['ssl'] is not None else 'khong'}, workers={args.workers})",
        flush=True,
    )
    conn = connect(settings, autocommit=True)
    try:
        for source_name, table_name, table_dir in plan:
            dest_name = target_table_name(source_name, table_name, full_prefix=args.full_prefix)
            print(f"\n== {source_name}/{table_name} -> {dest_name}", flush=True)
            try:
                conn.ping(reconnect=False)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                conn = connect(settings, autocommit=True)
            load_table(
                conn,
                settings,
                source_name,
                table_name,
                table_dir,
                args.workers,
                state,
                full_prefix=args.full_prefix,
            )
    finally:
        conn.close()
    print("\nHoan tat.", flush=True)
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Nap parquet vao MySQL cloud (khong xoa nguon).")
    parser.add_argument("--source", choices=["samples", "full", "all"], default="all")
    parser.add_argument("--full-dir", default="", help="Thu muc thay the cho full_data (vd: full_data_clean)")
    parser.add_argument("--full-prefix", default="", help="Tien to ten bang cho source=full (mac dinh khong tien to)")
    parser.add_argument("--tables", default="", help="Danh sach bang, cach nhau bang dau phay (vd: books,interactions)")
    parser.add_argument("--dry-run", action="store_true", help="Chi in so dong va dung luong, khong ket noi MySQL")
    parser.add_argument("--workers", type=int, default=3, help="So luong ket noi song song theo file parquet (mac dinh: 3)")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_FILE), help="File luu trang thai file da nap de resume")
    parser.add_argument("--no-resume-state", action="store_true", help="Tat file trang thai resume")
    return run(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
