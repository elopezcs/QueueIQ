import re
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from API.rag.db import init_rag_db
except ModuleNotFoundError:
    init_rag_db = None
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


def _pg_database_url() -> str | None:
    return settings.rag_database_url or settings.database_url


class _CompatCursor:
    def __init__(self, cursor: psycopg2.extensions.cursor) -> None:
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()


class _CompatPgConnection:
    def __init__(self, conn: psycopg2.extensions.connection) -> None:
        self._conn = conn
        self.row_factory = None

    def _rewrite_upsert(self, sql: str) -> str:
        lowered = sql.lower()
        if "insert or replace into outputs" in lowered:
            return """
                INSERT INTO outputs(
                  session_id, run_id, urgency_band, visit_category,
                  wait_p50_minutes, wait_p90_minutes, explanation,
                  disclaimers_json, config_snapshot_hash, created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (session_id) DO UPDATE
                SET run_id=EXCLUDED.run_id,
                    urgency_band=EXCLUDED.urgency_band,
                    visit_category=EXCLUDED.visit_category,
                    wait_p50_minutes=EXCLUDED.wait_p50_minutes,
                    wait_p90_minutes=EXCLUDED.wait_p90_minutes,
                    explanation=EXCLUDED.explanation,
                    disclaimers_json=EXCLUDED.disclaimers_json,
                    config_snapshot_hash=EXCLUDED.config_snapshot_hash,
                    created_at=EXCLUDED.created_at
            """
        if "insert or replace into appointments" in lowered:
            return """
                INSERT INTO appointments(
                    appointment_id, patient_id, clinic_id, session_id, scheduled_for, status, description, created_at, updated_at
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (appointment_id) DO UPDATE
                SET patient_id=EXCLUDED.patient_id,
                    clinic_id=EXCLUDED.clinic_id,
                    session_id=EXCLUDED.session_id,
                    scheduled_for=EXCLUDED.scheduled_for,
                    status=EXCLUDED.status,
                    description=EXCLUDED.description,
                    created_at=EXCLUDED.created_at,
                    updated_at=EXCLUDED.updated_at
            """
        if "insert or replace into sessions" in lowered:
            return """
                INSERT INTO sessions(session_id, clinic_id, patient_id, created_at, done)
                VALUES(%s,%s,%s,%s,1)
                ON CONFLICT (session_id) DO UPDATE
                SET clinic_id=EXCLUDED.clinic_id,
                    patient_id=EXCLUDED.patient_id,
                    created_at=EXCLUDED.created_at,
                    done=EXCLUDED.done
            """
        return sql

    def _rewrite_sql(self, sql: str) -> str:
        rewritten = self._rewrite_upsert(sql)
        rewritten = rewritten.replace('""', "''")
        rewritten = rewritten.replace("?", "%s")
        rewritten = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", rewritten, flags=re.IGNORECASE)
        return rewritten

    def execute(self, sql: str, params=None):
        cursor = self._conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(self._rewrite_sql(sql), params or ())
        return _CompatCursor(cursor)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def get_conn() -> sqlite3.Connection | _CompatPgConnection:
    pg_url = _pg_database_url()
    if pg_url:
        conn = psycopg2.connect(pg_url)
        return _CompatPgConnection(conn)

    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection | _CompatPgConnection, table_name: str, column_name: str, column_sql: str) -> None:
    if not isinstance(conn, sqlite3.Connection):
        return
    columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()}
    if column_name not in columns:
        conn.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}')


def init_db() -> None:
    from app.storage.repo import seed_demo_data
    from app.storage.schema import schema_sql

    pg_url = _pg_database_url()
    if pg_url:
        if callable(init_rag_db):
            init_rag_db()
        if settings.env.lower() != 'prod':
            seed_demo_data()
        return

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
