import re

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from API.rag.db import init_rag_db
except ModuleNotFoundError:
    init_rag_db = None
from app.core.settings import settings


def _pg_database_url() -> str | None:
    return settings.rag_database_url or settings.database_url


def _required_database_url() -> str:
    url = _pg_database_url()
    if url:
        return url
    raise RuntimeError(
        'DATABASE_URL (or RAG_DATABASE_URL) is not configured. File-based SQLite fallback has been removed.'
    )


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
        if 'insert or replace into outputs' in lowered:
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
        if 'insert or replace into appointments' in lowered:
            return """
                INSERT INTO appointments(
                    appointment_id, booking_token, patient_id, clinic_id, session_id, scheduled_for, status, description, created_at, updated_at
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (appointment_id) DO UPDATE
                SET booking_token=EXCLUDED.booking_token,
                    patient_id=EXCLUDED.patient_id,
                    clinic_id=EXCLUDED.clinic_id,
                    session_id=EXCLUDED.session_id,
                    scheduled_for=EXCLUDED.scheduled_for,
                    status=EXCLUDED.status,
                    description=EXCLUDED.description,
                    created_at=EXCLUDED.created_at,
                    updated_at=EXCLUDED.updated_at
            """
        if 'insert or replace into sessions' in lowered:
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
        rewritten = rewritten.replace('?', '%s')
        rewritten = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'BIGSERIAL PRIMARY KEY', rewritten, flags=re.IGNORECASE)
        return rewritten

    def execute(self, sql: str, params=None):
        cursor = self._conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(self._rewrite_sql(sql), params or ())
        return _CompatCursor(cursor)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def get_conn() -> _CompatPgConnection:
    conn = psycopg2.connect(_required_database_url())
    return _CompatPgConnection(conn)


def init_db() -> None:
    _required_database_url()
    if not callable(init_rag_db):
        raise RuntimeError('RAG DB initializer is unavailable in this runtime')

    init_rag_db()
