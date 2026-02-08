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


def init_db() -> None:
    from app.storage.schema import schema_sql

    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        conn.executescript(schema_sql())
        conn.commit()
    finally:
        conn.close()
