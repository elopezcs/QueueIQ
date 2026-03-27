import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from API.rag.db import execute, fetch_all, init_rag_db, pgvector_enabled, rag_db_enabled, to_vector_literal
from API.rag.model_adapters.registry import db_models_or_default, embed_text, persist_model_registry
from API.rag.orchestrators.rag_orchestrator import RagOrchestrator, RagTurnResult
from API.rag.prompts.templates import DEFAULT_RAG_DISCLAIMERS


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


logger = logging.getLogger("queueiq.rag")


class RagService:
    def __init__(self) -> None:
        self.db_ready, self.pgvector_enabled = init_rag_db()
        persist_model_registry()
        self._ensure_prompt_versions()
        self.orchestrator = RagOrchestrator()

    def _ensure_prompt_versions(self) -> None:
        if not rag_db_enabled():
            return
        execute(
            """
            INSERT INTO rag.prompt_versions(prompt_version, model_key, system_template, user_template, active)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT (prompt_version) DO UPDATE
              SET model_key=EXCLUDED.model_key,
                  system_template=EXCLUDED.system_template,
                  user_template=EXCLUDED.user_template,
                  active=EXCLUDED.active
            """,
            (
                "gemma_v1",
                "gemma3_4b",
                "Use retrieved context only. Return JSON.",
                "Answer using patient and clinic context with safety fallback.",
                True,
            ),
        )
        execute(
            """
            INSERT INTO rag.prompt_versions(prompt_version, model_key, system_template, user_template, active)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT (prompt_version) DO UPDATE
              SET model_key=EXCLUDED.model_key,
                  system_template=EXCLUDED.system_template,
                  user_template=EXCLUDED.user_template,
                  active=EXCLUDED.active
            """,
            (
                "qwen_v1",
                "qwen2_5_7b_instruct",
                "Use retrieved context only. Return strict JSON.",
                "Answer using patient and clinic context with safety fallback.",
                True,
            ),
        )

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "database_ready": bool(self.db_ready),
            "pgvector_enabled": bool(self.pgvector_enabled),
        }

    def models(self) -> list[dict[str, Any]]:
        return db_models_or_default()

    def start_session(
        self,
        *,
        patient_id: str,
        clinic_id: str,
        patient_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Keep auth-source patients and rag.patients aligned so FK constraints
        # do not fail when a user starts a RAG session before seeding.
        full_name = str((patient_profile or {}).get("full_name") or patient_id).strip() or patient_id
        sex_value = (patient_profile or {}).get("sex")
        sex = str(sex_value).strip() if isinstance(sex_value, str) and sex_value.strip() else None
        execute(
            """
            INSERT INTO rag.patients(patient_id, full_name, sex)
            VALUES(%s,%s,%s)
            ON CONFLICT (patient_id) DO UPDATE
              SET full_name=EXCLUDED.full_name,
                  sex=COALESCE(rag.patients.sex, EXCLUDED.sex)
            """,
            (patient_id, full_name, sex),
        )

        session_id = f"rag_sess_{secrets.token_hex(12)}"
        execute(
            "INSERT INTO rag.patient_chat_sessions(session_id, patient_id, clinic_id, started_at) VALUES(%s,%s,%s,%s)",
            (session_id, patient_id, clinic_id, _now_iso()),
        )
        logger.info("RAG session started: session_id=%s patient_id=%s clinic_id=%s", session_id, patient_id, clinic_id)
        first = (
            "I can help with clinic guidance using your profile context and clinic policies. "
            "I cannot diagnose or prescribe. What would you like to ask?"
        )
        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "assistant", first, _now_iso()),
        )
        return {"session_id": session_id, "assistant_message": first, "disclaimers": DEFAULT_RAG_DISCLAIMERS}

    def _session(self, session_id: str) -> dict[str, Any] | None:
        rows = fetch_all(
            "SELECT session_id, patient_id, clinic_id, started_at, ended_at FROM rag.patient_chat_sessions WHERE session_id=%s LIMIT 1",
            (session_id,),
        )
        return rows[0] if rows else None

    def turn(self, *, patient_id: str, session_id: str, user_message: str) -> RagTurnResult:
        session = self._session(session_id)
        if not session:
            raise ValueError("SESSION_NOT_FOUND")
        if session["patient_id"] != patient_id:
            raise PermissionError("SESSION_PATIENT_MISMATCH")
        if session.get("ended_at"):
            raise RuntimeError("SESSION_ENDED")

        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "user", user_message, _now_iso()),
        )
        result = self.orchestrator.run_turn(
            session_id=session_id,
            patient_id=patient_id,
            clinic_id=session["clinic_id"],
            user_message=user_message,
        )
        logger.info(
            "RAG turn processed: session_id=%s patient_id=%s route=%s done=%s",
            session_id,
            patient_id,
            result.route,
            result.done,
        )
        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "assistant", result.assistant_message, _now_iso()),
        )
        return result

    def end(self, *, patient_id: str, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        if not session:
            raise ValueError("SESSION_NOT_FOUND")
        if session["patient_id"] != patient_id:
            raise PermissionError("SESSION_PATIENT_MISMATCH")
        if not session.get("ended_at"):
            execute(
                "UPDATE rag.patient_chat_sessions SET ended_at=%s WHERE session_id=%s",
                (_now_iso(), session_id),
            )
        traces = fetch_all(
            """
            SELECT trace_id, context_preview
            FROM rag.retrieval_traces
            WHERE session_id=%s
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (session_id,),
        )
        sources = []
        for trace in traces[:5]:
            sources.append(
                {
                    "source_type": "trace",
                    "source_id": trace["trace_id"],
                    "snippet": str(trace["context_preview"])[:240],
                }
            )
        summary = "Session finalized. Context sources were captured for traceability."
        logger.info("RAG session ended: session_id=%s patient_id=%s trace_sources=%s", session_id, patient_id, len(sources))
        return {"session_id": session_id, "ended": True, "final_summary": summary, "sources": sources}

    def session_detail(self, *, patient_id: str, session_id: str) -> dict[str, Any] | None:
        session = self._session(session_id)
        if not session or session["patient_id"] != patient_id:
            return None
        messages = fetch_all(
            """
            SELECT role, content, created_at
            FROM rag.patient_chat_messages
            WHERE session_id=%s
            ORDER BY id ASC
            """,
            (session_id,),
        )
        session["messages"] = messages
        return session

    def trace_detail(self, trace_id: str) -> dict[str, Any] | None:
        rows = fetch_all(
            """
            SELECT trace_id, session_id, patient_id, clinic_id, route, query_text, context_preview, created_at
            FROM rag.retrieval_traces WHERE trace_id=%s LIMIT 1
            """,
            (trace_id,),
        )
        return rows[0] if rows else None

    def seed(self) -> dict[str, Any]:
        if not rag_db_enabled():
            return {"ok": False, "patients_seeded": 0, "clinics_seeded": 0, "notes": ["DATABASE_URL not configured"]}

        clinics = [
            ("clinic_north", "QueueIQ North Clinic", "Dallas"),
            ("clinic_central", "QueueIQ Central Clinic", "Austin"),
            ("clinic_west", "QueueIQ West Clinic", "Phoenix"),
        ]
        for clinic_id, name, city in clinics:
            execute(
                """
                INSERT INTO rag.clinics(clinic_id, clinic_name, city, timezone)
                VALUES(%s,%s,%s,%s)
                ON CONFLICT (clinic_id) DO UPDATE SET clinic_name=EXCLUDED.clinic_name, city=EXCLUDED.city
                """,
                (clinic_id, name, city, "America/Chicago"),
            )
        for clinic_id, _, _ in clinics:
            execute("DELETE FROM rag.clinic_faqs WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_rules WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_hours_services WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_documents WHERE clinic_id=%s", (clinic_id,))

        for idx, clinic in enumerate(clinics, start=1):
            clinic_id = clinic[0]
            execute(
                """
                INSERT INTO rag.clinic_faqs(faq_id, clinic_id, question, answer)
                VALUES(%s,%s,%s,%s)
                """,
                (f"faq_{clinic_id}_1", clinic_id, "Do you accept walk-ins?", "Yes, walk-ins are accepted based on capacity."),
            )
            execute(
                """
                INSERT INTO rag.clinic_rules(rule_id, clinic_id, rule_name, rule_text)
                VALUES(%s,%s,%s,%s)
                """,
                (
                    f"rule_{clinic_id}_1",
                    clinic_id,
                    "Medication refill policy",
                    "Refills require physician review; urgent refill requests are escalated to staff.",
                ),
            )
            execute(
                """
                INSERT INTO rag.clinic_hours_services(id, clinic_id, day_of_week, open_time, close_time, service_name)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (f"hours_{clinic_id}_1", clinic_id, "Monday-Friday", "08:00", "18:00", "Primary care"),
            )
            execute(
                """
                INSERT INTO rag.clinic_documents(document_id, clinic_id, doc_type, title, body, effective_date)
                VALUES(%s,%s,%s,%s,%s,%s)
                ON CONFLICT (document_id) DO UPDATE SET body=EXCLUDED.body, effective_date=EXCLUDED.effective_date
                """,
                (
                    f"doc_{clinic_id}_sop",
                    clinic_id,
                    "sop",
                    f"{clinic[1]} triage SOP",
                    "Patients with chest pain, severe shortness of breath, or stroke-like symptoms must be escalated immediately.",
                    datetime.now(timezone.utc).date().isoformat(),
                ),
            )
            execute("DELETE FROM rag.clinic_document_chunks WHERE document_id=%s", (f"doc_{clinic_id}_sop",))
            sop_chunks = [
                "Emergency indicators include chest pain, severe shortness of breath, seizure, and stroke-like symptoms.",
                "Medication refill requests are triaged and routed to clinician review.",
                "Walk-in arrivals are accepted based on live queue capacity and triage priority.",
            ]
            for order, chunk in enumerate(sop_chunks, start=1):
                chunk_id = f"chunk_{clinic_id}_{order}"
                if pgvector_enabled():
                    vector_literal = to_vector_literal(embed_text(chunk))
                    execute(
                        """
                        INSERT INTO rag.clinic_document_chunks(chunk_id, document_id, clinic_id, chunk_text, chunk_order, embedding)
                        VALUES(%s,%s,%s,%s,%s,%s::vector)
                        """,
                        (chunk_id, f"doc_{clinic_id}_sop", clinic_id, chunk, order, vector_literal),
                    )
                else:
                    execute(
                        """
                        INSERT INTO rag.clinic_document_chunks(chunk_id, document_id, clinic_id, chunk_text, chunk_order, embedding_text)
                        VALUES(%s,%s,%s,%s,%s,%s)
                        """,
                        (chunk_id, f"doc_{clinic_id}_sop", clinic_id, chunk, order, chunk),
                    )

        base_date = datetime.now(timezone.utc) - timedelta(days=40)
        patients = [
            ("pat_anna", "Anna Morales", "F"),
            ("pat_jordan", "Jordan Lee", "M"),
            ("pat_riley", "Riley Chen", "F"),
        ]
        for p_id, name, sex in patients:
            execute(
                """
                INSERT INTO rag.patients(patient_id, full_name, date_of_birth, sex)
                VALUES(%s,%s,%s,%s)
                ON CONFLICT (patient_id) DO UPDATE SET full_name=EXCLUDED.full_name, sex=EXCLUDED.sex
                """,
                (p_id, name, "1988-01-01", sex),
            )
            execute("DELETE FROM rag.encounters WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.medications WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.allergies WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.problem_list WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.clinical_notes WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.lab_summaries WHERE patient_id=%s", (p_id,))

            encounter_id = f"enc_{p_id}_1"
            clinic_id = clinics[(hash(p_id) % len(clinics))][0]
            execute(
                """
                INSERT INTO rag.encounters(encounter_id, patient_id, clinic_id, encounter_type, encounter_date, summary)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (encounter_id, p_id, clinic_id, "follow_up", (base_date + timedelta(days=10)).isoformat(), "Follow-up for chronic condition monitoring."),
            )
            execute(
                """
                INSERT INTO rag.medications(medication_id, patient_id, medication_name, dosage, frequency, start_date, active)
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                """,
                (f"med_{p_id}_1", p_id, "Lisinopril", "10mg", "daily", "2025-01-10", True),
            )
            execute(
                """
                INSERT INTO rag.allergies(allergy_id, patient_id, allergen, reaction, severity, active)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (f"alg_{p_id}_1", p_id, "Penicillin", "Rash", "moderate", True),
            )
            execute(
                """
                INSERT INTO rag.problem_list(problem_id, patient_id, problem_name, status, onset_date, notes)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (f"prob_{p_id}_1", p_id, "Hypertension", "active", "2022-05-01", "Controlled with medication."),
            )
            execute(
                """
                INSERT INTO rag.clinical_notes(note_id, patient_id, encounter_id, note_type, content)
                VALUES(%s,%s,%s,%s,%s)
                """,
                (f"note_{p_id}_1", p_id, encounter_id, "progress", "Patient reports occasional headaches; no red-flag neurological symptoms."),
            )
            execute(
                """
                INSERT INTO rag.lab_summaries(lab_summary_id, patient_id, test_name, summary, test_date)
                VALUES(%s,%s,%s,%s,%s)
                """,
                (f"lab_{p_id}_1", p_id, "Lipid panel", "LDL mildly elevated; recommend routine follow-up.", (base_date + timedelta(days=5)).isoformat()),
            )

        return {
            "ok": True,
            "patients_seeded": len(patients),
            "clinics_seeded": len(clinics),
            "notes": [
                "Synthetic seed data refreshed.",
                "Supports patient-only, clinic-only, mixed retrieval, and guardrail testing.",
            ],
        }


_SERVICE: RagService | None = None


def get_rag_service() -> RagService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RagService()
    return _SERVICE

