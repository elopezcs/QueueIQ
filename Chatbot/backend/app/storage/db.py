import sqlite3
from pathlib import Path

from app.core.settings import settings

_DB_PATH = None
_BACKEND_DIR = Path(__file__).resolve().parents[2]


def db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        raw_path = Path(settings.sqlite_path)
        if not raw_path.is_absolute():
            raw_path = _BACKEND_DIR / raw_path
        _DB_PATH = raw_path.resolve()
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
        _ensure_column(conn, 'patients', 'role', "TEXT NOT NULL DEFAULT 'patient'")
        _ensure_column(conn, 'patients', 'clinic_id', 'TEXT')
        _ensure_column(conn, 'patients', 'password_hash', 'TEXT')
        _ensure_column(conn, 'patients', 'medical_profile_json', 'TEXT')
        _ensure_column(conn, 'patients', 'professional_profile_json', 'TEXT')
        _ensure_column(conn, 'appointments', 'description', 'TEXT')
        conn.execute(
            """
            UPDATE patients
            SET role = CASE
                WHEN COALESCE(role, '') = '' AND is_admin = 1 THEN 'manager'
                WHEN COALESCE(role, '') = '' THEN 'patient'
                ELSE role
            END
            """
        )
        conn.execute(
            "UPDATE patients SET is_admin = CASE WHEN role = 'manager' THEN 1 ELSE 0 END"
        )
        conn.commit()
    finally:
        conn.close()

    if settings.env.lower() != 'prod':
        seed_demo_data()
