"""Lọc k-core trên bảng tương tác (user_id, book_id).

Lặp cho đến khi ổn định: giữ user và sách có ít nhất k tương tác trong tập còn lại.
Chỉ giữ 2 cột (user_id, book_id) và cắt DAG bằng localCheckpoint qua từng vòng
để tránh phình lineage / tràn bộ nhớ trên tập dữ liệu hàng trăm triệu dòng.
"""
import logging

from pyspark import StorageLevel
from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def _count_stats(df: DataFrame) -> dict:
    # Tách count riêng thay vì countDistinct kép để tránh Spark nhân đôi dữ liệu (Expand)
    rows = df.count()
    if rows == 0:
        return {'rows': 0, 'users': 0, 'books': 0}
    users = df.select('user_id').distinct().count()
    books = df.select('book_id').distinct().count()
    return {'rows': int(rows), 'users': int(users), 'books': int(books)}


def _cut_lineage(df: DataFrame) -> DataFrame:
    try:
        return df.localCheckpoint(eager=True)
    except Exception:
        out = df.persist(StorageLevel.DISK_ONLY)
        out.count()
        return out


def k_core(df_interactions: DataFrame, k: int = 5, max_iter: int = 50):
    """Trả về (df_kept, kept_user_ids, kept_book_ids, stats).

    df_interactions phải có cột user_id và book_id. Mỗi dòng là một tương tác.
    """
    if k <= 0:
        before = _count_stats(df_interactions)
        kept_users = df_interactions.select('user_id').distinct()
        kept_books = df_interactions.select('book_id').distinct()
        stats = {
            'k': k,
            'iterations': 0,
            'converged': True,
            'before': before,
            'after': before,
            'before_rows': before['rows'],
            'after_rows': before['rows'],
        }
        return df_interactions, kept_users, kept_books, stats

    # Thu gọn về đúng 2 cột khóa trước khi lặp để giảm ~60% dữ liệu shuffle mỗi vòng
    current = _cut_lineage(df_interactions.select('user_id', 'book_id'))
    before = _count_stats(current)
    logging.info(f"K-core (k={k}) bắt đầu: {before}")

    prev_rows = before['rows']
    converged = prev_rows == 0
    iteration = 0

    if not converged:
        for iteration in range(1, max_iter + 1):
            users = current.groupBy('user_id').count().filter(F.col('count') >= k).select('user_id')
            books = current.groupBy('book_id').count().filter(F.col('count') >= k).select('book_id')
            nxt = _cut_lineage(
                current
                .join(users, on='user_id', how='left_semi')
                .join(books, on='book_id', how='left_semi')
            )
            new_rows = nxt.count()
            current.unpersist()
            current = nxt
            logging.info(f"K-core vòng {iteration}: còn {new_rows} tương tác (bỏ {prev_rows - new_rows})")
            if new_rows == prev_rows:
                converged = True
                break
            prev_rows = new_rows

        if not converged:
            logging.warning(f"K-core chưa ổn định sau {max_iter} vòng")

    kept_users = _cut_lineage(current.select('user_id').distinct())
    kept_books = _cut_lineage(current.select('book_id').distinct())
    after = {
        'rows': int(current.count()),
        'users': int(kept_users.count()),
        'books': int(kept_books.count()),
    }
    if set(df_interactions.columns) == {'user_id', 'book_id'}:
        df_kept = _cut_lineage(current)
    else:
        df_kept = (df_interactions
                   .join(kept_users, on='user_id', how='left_semi')
                   .join(kept_books, on='book_id', how='left_semi'))
    current.unpersist()

    stats = {
        'k': k,
        'iterations': iteration,
        'converged': converged,
        'before': before,
        'after': after,
        'before_rows': before['rows'],
        'after_rows': after['rows'],
    }
    logging.info(f"K-core xong: {stats}")
    return df_kept, kept_users, kept_books, stats
