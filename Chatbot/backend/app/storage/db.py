import sqlite3
from pathlib import Path

from app.core.settings import settings

_DB_PATH = None


def db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = Path(settings.sqlite_path).resolve()
    return _DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
    columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()}
    if column_name not in columns:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}')


def init_db() -> None:
    from app.storage.repo import seed_demo_data
    from app.storage.schema import schema_sql

    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        conn.executescript(schema_sql())
        _ensure_column(conn, 'sessions', 'patient_id', 'TEXT')
        _ensure_column(conn, 'patients', 'is_admin', 'INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    finally:
        conn.close()

    if settings.env.lower() != 'prod':
        seed_demo_data()
