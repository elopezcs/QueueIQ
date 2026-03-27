import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from Chatbot.backend.app.core.settings import settings

_DB_READY = False
_PGVECTOR_ENABLED = False


def _database_url() -> str | None:
    return settings.rag_database_url or settings.database_url or os.getenv("RAG_DATABASE_URL") or os.getenv("DATABASE_URL")


def rag_db_enabled() -> bool:
    return bool(_database_url())


@contextmanager
def get_conn() -> Iterator[psycopg2.extensions.connection]:
    url = _database_url()
    print(url)
    if not url:
        raise RuntimeError("DATABASE_URL (or RAG_DATABASE_URL) is not configured")
    conn = psycopg2.connect(url)
    try:
        yield conn
    finally:
        conn.close()


def _table_sql(has_vector: bool) -> str:
    chunk_embedding_column = (
        f"embedding vector({settings.rag_vector_dimensions})"
        if has_vector
        else "embedding_text TEXT"
    )
    return f"""
CREATE SCHEMA IF NOT EXISTS rag;

CREATE TABLE IF NOT EXISTS rag.patients (
  patient_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  date_of_birth DATE,
  sex TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.encounters (
  encounter_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  clinic_id TEXT NOT NULL,
  encounter_type TEXT NOT NULL,
  encounter_date TIMESTAMPTZ NOT NULL,
  summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag.medications (
  medication_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  medication_name TEXT NOT NULL,
  dosage TEXT,
  frequency TEXT,
  start_date DATE,
  end_date DATE,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rag.allergies (
  allergy_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  allergen TEXT NOT NULL,
  reaction TEXT,
  severity TEXT,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS rag.problem_list (
  problem_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  problem_name TEXT NOT NULL,
  status TEXT NOT NULL,
  onset_date DATE,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS rag.clinical_notes (
  note_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  encounter_id TEXT REFERENCES rag.encounters(encounter_id),
  note_type TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.lab_summaries (
  lab_summary_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  test_name TEXT NOT NULL,
  summary TEXT NOT NULL,
  test_date TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS rag.patient_chat_sessions (
  session_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  clinic_id TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag.patient_chat_messages (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES rag.patient_chat_sessions(session_id),
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.clinics (
  clinic_id TEXT PRIMARY KEY,
  clinic_name TEXT NOT NULL,
  city TEXT,
  timezone TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.clinic_documents (
  document_id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  doc_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  effective_date DATE
);

CREATE TABLE IF NOT EXISTS rag.clinic_document_chunks (
  chunk_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES rag.clinic_documents(document_id),
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  chunk_text TEXT NOT NULL,
  chunk_order INTEGER NOT NULL,
  {chunk_embedding_column}
);

CREATE TABLE IF NOT EXISTS rag.clinic_faqs (
  faq_id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  question TEXT NOT NULL,
  answer TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag.clinic_rules (
  rule_id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  rule_name TEXT NOT NULL,
  rule_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag.clinic_hours_services (
  id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  day_of_week TEXT NOT NULL,
  open_time TEXT,
  close_time TEXT,
  service_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag.retrieval_traces (
  trace_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  clinic_id TEXT NOT NULL,
  route TEXT NOT NULL,
  query_text TEXT NOT NULL,
  context_preview TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.llm_runs (
  run_id TEXT PRIMARY KEY,
  trace_id TEXT REFERENCES rag.retrieval_traces(trace_id),
  session_id TEXT NOT NULL,
  model_key TEXT NOT NULL,
  provider TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  prompt_preview TEXT NOT NULL,
  response_preview TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.prompt_versions (
  prompt_version TEXT PRIMARY KEY,
  model_key TEXT NOT NULL,
  system_template TEXT NOT NULL,
  user_template TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.model_configs (
  model_key TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model_name TEXT NOT NULL,
  prompt_variant TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  metadata_json JSONB NOT NULL DEFAULT '{{}}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_rag_encounters_patient_date ON rag.encounters(patient_id, encounter_date DESC);
CREATE INDEX IF NOT EXISTS idx_rag_medications_patient ON rag.medications(patient_id);
CREATE INDEX IF NOT EXISTS idx_rag_allergies_patient ON rag.allergies(patient_id);
CREATE INDEX IF NOT EXISTS idx_rag_problem_list_patient ON rag.problem_list(patient_id);
CREATE INDEX IF NOT EXISTS idx_rag_notes_patient ON rag.clinical_notes(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_labs_patient ON rag.lab_summaries(patient_id, test_date DESC);
CREATE INDEX IF NOT EXISTS idx_rag_sessions_patient ON rag.patient_chat_sessions(patient_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_messages_session ON rag.patient_chat_messages(session_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_clinic_doc ON rag.clinic_document_chunks(clinic_id, document_id);
CREATE INDEX IF NOT EXISTS idx_rag_faqs_clinic ON rag.clinic_faqs(clinic_id);
CREATE INDEX IF NOT EXISTS idx_rag_rules_clinic ON rag.clinic_rules(clinic_id);
CREATE INDEX IF NOT EXISTS idx_rag_hours_clinic ON rag.clinic_hours_services(clinic_id);
"""


def init_rag_db() -> tuple[bool, bool]:
    global _DB_READY, _PGVECTOR_ENABLED
    if not rag_db_enabled():
        _DB_READY = False
        _PGVECTOR_ENABLED = False
        return False, False
    with get_conn() as conn:
        with conn.cursor() as cur:
            has_vector = False
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                has_vector = True
            except Exception:
                conn.rollback()
            cur.execute(_table_sql(has_vector))
            conn.commit()
            _DB_READY = True
            _PGVECTOR_ENABLED = has_vector
            return True, has_vector


def fetch_all(query: str, params: tuple | list | None = None) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def execute(query: str, params: tuple | list | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            conn.commit()


def pgvector_enabled() -> bool:
    return _PGVECTOR_ENABLED


def db_ready() -> bool:
    return _DB_READY


def to_vector_literal(values: list[float], dimensions: int | None = None) -> str:
    dims = int(dimensions or settings.rag_vector_dimensions)
    clean = [float(v) for v in values[:dims]]
    if len(clean) < dims:
        clean.extend([0.0] * (dims - len(clean)))
    return "[" + ",".join(f"{v:.8f}" for v in clean) + "]"

