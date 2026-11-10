import queue
import threading
import sqlite3
import pymysql
import pymysql.cursors
from fastapi import HTTPException
from app.core.config import settings

_mysql_pool: queue.LifoQueue = queue.LifoQueue(maxsize=settings.MYSQL_POOL_SIZE)
_mysql_pool_slots = threading.BoundedSemaphore(settings.MYSQL_POOL_SIZE)

class PooledConnection:
    # Tra ket noi ve pool khi close
    def __init__(self, connection):
        self._connection = connection
        self._returned = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def close(self):
        if self._returned:
            return
        self._returned = True
        try:
            if self._connection.open:
                _mysql_pool.put(self._connection)
            else:
                self._connection.close()
        finally:
            _mysql_pool_slots.release()

def _connect_mysql():
    # Tao ket noi moi toi MySQL
    return pymysql.connect(
        host=settings.DB_HOST,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=settings.MYSQL_POOL_TIMEOUT_SECONDS,
    )

def _get_pooled_mysql_connection():
    # Lay ket noi tu pool hoac khoi tao moi
    if not _mysql_pool_slots.acquire(timeout=settings.MYSQL_POOL_TIMEOUT_SECONDS):
        raise TimeoutError("Timed out waiting for a MySQL connection")

    try:
        try:
            connection = _mysql_pool.get_nowait()
        except queue.Empty:
            connection = _connect_mysql()
        else:
            try:
                connection.ping(reconnect=True)
            except Exception:
                connection.close()
                connection = _connect_mysql()
        return PooledConnection(connection)
    except Exception:
        _mysql_pool_slots.release()
        raise

class CompatibleSQLiteCursor(sqlite3.Cursor):
    # Ho tro context manager cho SQLite cursor
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class CompatibleSQLiteConnection(sqlite3.Connection):
    # Ket noi SQLite voi cursor ho tro context manager
    def cursor(self, factory=CompatibleSQLiteCursor):
        return super().cursor(factory=factory)

def get_conn():
    # Uu tien MySQL, fallback SQLite khi loi
    try:
        return "mysql", _get_pooled_mysql_connection()
    except TimeoutError as error:
        raise HTTPException(status_code=503, detail="Database connection pool is busy") from error
    except Exception:
        conn = sqlite3.connect(str(settings.SQLITE_PATH), factory=CompatibleSQLiteConnection)
        conn.row_factory = sqlite3.Row
        return "sqlite", conn

def close_pool():
    # Dong toan bo ket noi trong pool
    while True:
        try:
            _mysql_pool.get_nowait().close()
        except queue.Empty:
            break

