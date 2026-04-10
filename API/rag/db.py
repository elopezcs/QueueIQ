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
    patient_chunk_embedding_column = (
        f"embedding vector({settings.rag_vector_dimensions})"
        if has_vector
        else "embedding_text TEXT"
    )
    patient_chunk_vector_index_sql = (
        "CREATE INDEX IF NOT EXISTS idx_rag_patient_chunks_embedding "
        "ON rag.patient_context_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);"
        if has_vector
        else ""
    )
    return f"""
CREATE TABLE IF NOT EXISTS patients (
  patient_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  email_verified INTEGER NOT NULL DEFAULT 0,
  is_admin INTEGER NOT NULL DEFAULT 0,
  role TEXT NOT NULL DEFAULT 'patient',
  clinic_id TEXT,
  password_hash TEXT,
  medical_profile_json TEXT,
  professional_profile_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL,
  patient_id TEXT,
  created_at TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS messages (
  id BIGSERIAL PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  ts TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS outputs (
  session_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  urgency_band TEXT NOT NULL,
  visit_category TEXT NOT NULL,
  wait_p50_minutes INTEGER NOT NULL,
  wait_p90_minutes INTEGER NOT NULL,
  explanation TEXT NOT NULL,
  disclaimers_json TEXT NOT NULL,
  config_snapshot_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS auth_otps (
  id BIGSERIAL PRIMARY KEY,
  patient_id TEXT NOT NULL,
  email TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  used_at TEXT,
  FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS auth_sessions (
  token TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  FOREIGN KEY(patient_id) REFERENCES patients(patient_id)
);

CREATE TABLE IF NOT EXISTS appointments (
  appointment_id TEXT PRIMARY KEY,
  booking_token TEXT UNIQUE,
  patient_id TEXT NOT NULL,
  clinic_id TEXT NOT NULL,
  session_id TEXT,
  scheduled_for TEXT NOT NULL,
  status TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(patient_id) REFERENCES patients(patient_id),
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS notification_logs (
  id BIGSERIAL PRIMARY KEY,
  appointment_id TEXT NOT NULL,
  notification_type TEXT NOT NULL,
  scheduled_for TEXT NOT NULL,
  sent_at TEXT,
  status TEXT NOT NULL,
  detail TEXT,
  FOREIGN KEY(appointment_id) REFERENCES appointments(appointment_id)
);

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

CREATE TABLE IF NOT EXISTS rag.patient_context_chunks (
  chunk_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  chunk_text TEXT NOT NULL,
  chunk_order INTEGER NOT NULL,
  {patient_chunk_embedding_column},
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

CREATE TABLE IF NOT EXISTS rag.chat_turns (
  turn_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES rag.patient_chat_sessions(session_id),
  patient_id TEXT NOT NULL REFERENCES rag.patients(patient_id),
  clinic_id TEXT NOT NULL REFERENCES rag.clinics(clinic_id),
  turn_index INTEGER NOT NULL,
  route TEXT NOT NULL,
  status TEXT NOT NULL,
  user_message_id BIGINT REFERENCES rag.patient_chat_messages(id),
  assistant_message_id BIGINT REFERENCES rag.patient_chat_messages(id),
  trace_id TEXT,
  run_id TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  latency_ms INTEGER
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
  turn_id TEXT,
  session_id TEXT NOT NULL,
  patient_id TEXT NOT NULL,
  clinic_id TEXT NOT NULL,
  route TEXT NOT NULL,
  query_text TEXT NOT NULL,
  context_preview TEXT NOT NULL,
  retrieval_strategy TEXT NOT NULL DEFAULT 'hybrid',
  source_count_patient INTEGER NOT NULL DEFAULT 0,
  source_count_clinic INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.llm_runs (
  run_id TEXT PRIMARY KEY,
  turn_id TEXT,
  trace_id TEXT REFERENCES rag.retrieval_traces(trace_id),
  session_id TEXT NOT NULL,
  model_key TEXT NOT NULL,
  model_name TEXT,
  provider TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  prompt_preview TEXT NOT NULL,
  response_preview TEXT NOT NULL,
  prompt_hash TEXT,
  response_hash TEXT,
  status TEXT NOT NULL DEFAULT 'ok',
  error_type TEXT,
  error_message TEXT,
  latency_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rag.chat_outputs (
  session_id TEXT PRIMARY KEY REFERENCES rag.patient_chat_sessions(session_id),
  run_id TEXT NOT NULL,
  urgency_band TEXT NOT NULL,
  visit_category TEXT NOT NULL,
  wait_p50_minutes INTEGER NOT NULL,
  wait_p90_minutes INTEGER NOT NULL,
  explanation TEXT NOT NULL,
  disclaimers_json TEXT NOT NULL,
  config_snapshot_hash TEXT NOT NULL,
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

DROP TABLE IF EXISTS rag.prompt_versions;
DROP TABLE IF EXISTS rag.problem_list;

ALTER TABLE rag.retrieval_traces
  ADD COLUMN IF NOT EXISTS turn_id TEXT;
ALTER TABLE rag.retrieval_traces
  ADD COLUMN IF NOT EXISTS retrieval_strategy TEXT NOT NULL DEFAULT 'hybrid';
ALTER TABLE rag.retrieval_traces
  ADD COLUMN IF NOT EXISTS source_count_patient INTEGER NOT NULL DEFAULT 0;
ALTER TABLE rag.retrieval_traces
  ADD COLUMN IF NOT EXISTS source_count_clinic INTEGER NOT NULL DEFAULT 0;

ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS turn_id TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS model_name TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS prompt_hash TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS response_hash TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ok';
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS error_type TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS input_tokens INTEGER;
ALTER TABLE rag.llm_runs
  ADD COLUMN IF NOT EXISTS output_tokens INTEGER;

ALTER TABLE appointments
  ADD COLUMN IF NOT EXISTS booking_token TEXT;
UPDATE appointments
SET booking_token = 'BKG-' || UPPER(appointment_id)
WHERE COALESCE(booking_token, '') = '';

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_rag_chat_turns_trace') THEN
    ALTER TABLE rag.chat_turns
      ADD CONSTRAINT fk_rag_chat_turns_trace
      FOREIGN KEY (trace_id) REFERENCES rag.retrieval_traces(trace_id);
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_rag_chat_turns_run') THEN
    ALTER TABLE rag.chat_turns
      ADD CONSTRAINT fk_rag_chat_turns_run
      FOREIGN KEY (run_id) REFERENCES rag.llm_runs(run_id);
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_rag_retrieval_turn') THEN
    ALTER TABLE rag.retrieval_traces
      ADD CONSTRAINT fk_rag_retrieval_turn
      FOREIGN KEY (turn_id) REFERENCES rag.chat_turns(turn_id);
  END IF;
END$$;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_rag_llm_turn') THEN
    ALTER TABLE rag.llm_runs
      ADD CONSTRAINT fk_rag_llm_turn
      FOREIGN KEY (turn_id) REFERENCES rag.chat_turns(turn_id);
  END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_rag_encounters_patient_date ON rag.encounters(patient_id, encounter_date DESC);
CREATE INDEX IF NOT EXISTS idx_rag_medications_patient ON rag.medications(patient_id);
CREATE INDEX IF NOT EXISTS idx_rag_allergies_patient ON rag.allergies(patient_id);
CREATE INDEX IF NOT EXISTS idx_rag_notes_patient ON rag.clinical_notes(patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_labs_patient ON rag.lab_summaries(patient_id, test_date DESC);
CREATE INDEX IF NOT EXISTS idx_rag_patient_chunks_patient ON rag.patient_context_chunks(patient_id, source_type);
CREATE INDEX IF NOT EXISTS idx_rag_sessions_patient ON rag.patient_chat_sessions(patient_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_messages_session ON rag.patient_chat_messages(session_id, created_at ASC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_turns_session_turn_index ON rag.chat_turns(session_id, turn_index);
CREATE INDEX IF NOT EXISTS idx_rag_turns_patient_started ON rag.chat_turns(patient_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_turns_session_started ON rag.chat_turns(session_id, started_at ASC);
CREATE INDEX IF NOT EXISTS idx_rag_traces_turn ON rag.retrieval_traces(turn_id);
CREATE INDEX IF NOT EXISTS idx_rag_llm_runs_turn ON rag.llm_runs(turn_id);
CREATE INDEX IF NOT EXISTS idx_rag_llm_runs_session_created ON rag.llm_runs(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_llm_runs_model_created ON rag.llm_runs(model_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_clinic_doc ON rag.clinic_document_chunks(clinic_id, document_id);
CREATE INDEX IF NOT EXISTS idx_rag_faqs_clinic ON rag.clinic_faqs(clinic_id);
CREATE INDEX IF NOT EXISTS idx_rag_rules_clinic ON rag.clinic_rules(clinic_id);
CREATE INDEX IF NOT EXISTS idx_rag_hours_clinic ON rag.clinic_hours_services(clinic_id);
{patient_chunk_vector_index_sql}
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_outputs_session_id ON outputs(session_id);
CREATE INDEX IF NOT EXISTS idx_patients_email ON patients(email);
CREATE INDEX IF NOT EXISTS idx_auth_otps_email ON auth_otps(email);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_patient_id ON auth_sessions(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled_for ON appointments(scheduled_for);
CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_booking_token ON appointments(booking_token);
CREATE INDEX IF NOT EXISTS idx_notification_logs_appointment_id ON notification_logs(appointment_id);
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


def execute_fetch_one(query: str, params: tuple | list | None = None) -> dict | None:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None


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

