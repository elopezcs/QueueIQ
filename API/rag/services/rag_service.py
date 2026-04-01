import logging
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from API.rag.db import execute, fetch_all, init_rag_db, pgvector_enabled, rag_db_enabled, to_vector_literal
from API.rag.model_adapters.registry import db_models_or_default, embed_text, persist_model_registry
from API.rag.orchestrators.intake_orchestrator import RagIntakeOrchestrator
from API.rag.orchestrators.rag_orchestrator import RagOrchestrator
from Chatbot.backend.app.config.loader import get_clinic_by_id, load_clinics_config


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


logger = logging.getLogger("queueiq.rag")


class RagService:
    def __init__(self) -> None:
        self.db_ready, self.pgvector_enabled = init_rag_db()
        persist_model_registry()
        self._ensure_prompt_versions()
        self.orchestrator = RagOrchestrator()
        self.intake_orchestrator = RagIntakeOrchestrator()

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

    def _upsert_public_patient(self, *, patient_id: str, patient_profile: dict[str, Any] | None = None) -> None:
        profile = patient_profile or {}
        full_name = str(profile.get("full_name") or patient_id).strip() or patient_id
        email = str(profile.get("email") or f"{patient_id}@queueiq.local").strip().lower()
        role = str(profile.get("role") or "patient").strip().lower() or "patient"
        if role not in {"patient", "staff", "manager"}:
            role = "patient"
        is_admin = 1 if role == "manager" or bool(profile.get("is_admin")) else 0
        clinic_id = profile.get("clinic_id")
        if clinic_id is not None:
            clinic_id = str(clinic_id).strip() or None
        email_verified = 1 if bool(profile.get("email_verified")) else 0
        now = _now_iso()
        execute(
            """
            INSERT INTO patients(
                patient_id, full_name, email, email_verified, is_admin, role, clinic_id,
                password_hash, medical_profile_json, professional_profile_json, created_at, updated_at, last_login_at
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (patient_id) DO UPDATE
              SET full_name=EXCLUDED.full_name,
                  email=EXCLUDED.email,
                  email_verified=EXCLUDED.email_verified,
                  is_admin=EXCLUDED.is_admin,
                  role=EXCLUDED.role,
                  clinic_id=EXCLUDED.clinic_id,
                  updated_at=EXCLUDED.updated_at
            """,
            (
                patient_id,
                full_name,
                email,
                email_verified,
                is_admin,
                role,
                clinic_id,
                None,
                None,
                None,
                now,
                now,
                None,
            ),
        )

    def _insert_public_session(self, *, session_id: str, clinic_id: str, patient_id: str) -> None:
        execute(
            """
            INSERT INTO sessions(session_id, clinic_id, patient_id, created_at, done)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session_id, clinic_id, patient_id, _now_iso(), 0),
        )

    def _insert_public_message(self, *, session_id: str, role: str, content: str) -> None:
        execute(
            "INSERT INTO messages(session_id, role, content, ts) VALUES(%s,%s,%s,%s)",
            (session_id, role, content, _now_iso()),
        )

    def _mark_public_session_done(self, *, session_id: str) -> None:
        execute("UPDATE sessions SET done=1 WHERE session_id=%s", (session_id,))

    def _upsert_public_output(self, *, session_id: str, outputs: dict[str, Any]) -> None:
        execute(
            """
            INSERT INTO outputs(
                session_id, run_id, urgency_band, visit_category, wait_p50_minutes, wait_p90_minutes,
                explanation, disclaimers_json, config_snapshot_hash, created_at
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
            """,
            (
                session_id,
                outputs["run_id"],
                outputs["urgency_band"],
                outputs["visit_category"],
                int(outputs["wait_p50_minutes"]),
                int(outputs["wait_p90_minutes"]),
                outputs["explanation"],
                json.dumps(outputs["disclaimers"], ensure_ascii=False),
                outputs["config_snapshot_hash"],
                _now_iso(),
            ),
        )

    def _resolve_clinic(self, clinic_id: str) -> dict[str, Any] | None:
        clinic = get_clinic_by_id(clinic_id)
        if clinic:
            return clinic

        rows = fetch_all(
            """
            SELECT clinic_id, clinic_name, city
            FROM rag.clinics
            WHERE clinic_id = %s
            LIMIT 1
            """,
            (clinic_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "id": row["clinic_id"],
            "name": row["clinic_name"],
            "address_or_city": row.get("city") or "",
            "hours": {},
            "mock_capacity": {"servers_total": 3, "avg_service_minutes": 12},
        }

    def _patient_context_text(self, *, patient_id: str, query: str) -> str | None:
        items = self.orchestrator.patient_retriever.retrieve(patient_id=patient_id, query=query, limit=6)
        if not items:
            return None
        lines = []
        for item in items:
            source = str(item.get("source_type") or "context")
            snippet = str(item.get("snippet") or "").strip()
            if snippet:
                lines.append(f"- [{source}] {snippet}")
        return "\n".join(lines) if lines else None

    def _session_output_exists(self, session_id: str) -> bool:
        rows = fetch_all(
            "SELECT 1 FROM rag.chat_outputs WHERE session_id=%s LIMIT 1",
            (session_id,),
        )
        return bool(rows)

    def _transcript(self, session_id: str) -> list[dict[str, str]]:
        rows = fetch_all(
            """
            SELECT role, content
            FROM rag.patient_chat_messages
            WHERE session_id=%s
            ORDER BY id ASC
            """,
            (session_id,),
        )
        return [{"role": str(row["role"]), "content": str(row["content"])} for row in rows]

    def start_session(
        self,
        *,
        patient_id: str,
        clinic_id: str,
        patient_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clinic = self._resolve_clinic(clinic_id)
        if not clinic:
            raise ValueError("CLINIC_NOT_FOUND")

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
        self._upsert_public_patient(patient_id=patient_id, patient_profile=patient_profile)
        self._insert_public_session(session_id=session_id, clinic_id=clinic_id, patient_id=patient_id)
        logger.info("RAG session started: session_id=%s patient_id=%s clinic_id=%s", session_id, patient_id, clinic_id)
        patient_context = self._patient_context_text(
            patient_id=patient_id,
            query="medical profile history medications allergies",
        )
        first, disclaimers = self.intake_orchestrator.first_message(
            clinic=clinic,
            patient_context=patient_context,
        )
        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "assistant", first, _now_iso()),
        )
        self._insert_public_message(session_id=session_id, role="assistant", content=first)
        return {"session_id": session_id, "assistant_message": first, "disclaimers": disclaimers}

    def _session(self, session_id: str) -> dict[str, Any] | None:
        rows = fetch_all(
            "SELECT session_id, patient_id, clinic_id, started_at, ended_at FROM rag.patient_chat_sessions WHERE session_id=%s LIMIT 1",
            (session_id,),
        )
        return rows[0] if rows else None

    def turn(self, *, patient_id: str, session_id: str, user_message: str) -> dict[str, Any]:
        session = self._session(session_id)
        if not session:
            raise ValueError("SESSION_NOT_FOUND")
        if session["patient_id"] != patient_id:
            raise PermissionError("SESSION_PATIENT_MISMATCH")
        if session.get("ended_at") or self._session_output_exists(session_id):
            raise RuntimeError("SESSION_ENDED")

        clinic = self._resolve_clinic(str(session["clinic_id"]))
        if not clinic:
            raise ValueError("CLINIC_NOT_FOUND")

        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "user", user_message, _now_iso()),
        )
        self._insert_public_message(session_id=session_id, role="user", content=user_message)
        transcript = self._transcript(session_id)
        patient_context = self._patient_context_text(
            patient_id=patient_id,
            query=user_message,
        )
        assistant_message, done, progress = self.intake_orchestrator.next_turn(
            clinic=clinic,
            transcript=transcript,
            patient_context=patient_context,
        )
        logger.info(
            "RAG intake turn processed: session_id=%s patient_id=%s done=%s",
            session_id,
            patient_id,
            done,
        )
        execute(
            "INSERT INTO rag.patient_chat_messages(session_id, role, content, created_at) VALUES(%s,%s,%s,%s)",
            (session_id, "assistant", assistant_message, _now_iso()),
        )
        self._insert_public_message(session_id=session_id, role="assistant", content=assistant_message)
        if done:
            execute(
                "UPDATE rag.patient_chat_sessions SET ended_at=%s WHERE session_id=%s",
                (_now_iso(), session_id),
            )
            self._mark_public_session_done(session_id=session_id)
        return {
            "assistant_message": assistant_message,
            "done": done,
            "progress": progress,
        }

    def end(self, *, patient_id: str, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        if not session:
            raise ValueError("SESSION_NOT_FOUND")
        if session["patient_id"] != patient_id:
            raise PermissionError("SESSION_PATIENT_MISMATCH")
        if self._session_output_exists(session_id):
            raise RuntimeError("SESSION_FINALIZED")

        clinic = self._resolve_clinic(str(session["clinic_id"]))
        if not clinic:
            raise ValueError("CLINIC_NOT_FOUND")

        transcript = self._transcript(session_id)
        user_messages = [
            str(msg.get("content") or "")
            for msg in transcript
            if str(msg.get("role") or "").lower() == "user"
        ]
        patient_context = self._patient_context_text(
            patient_id=patient_id,
            query=" ".join(user_messages[-3:]).strip(),
        )
        outputs = self.intake_orchestrator.finalize(
            clinic=clinic,
            transcript=transcript,
            patient_context=patient_context,
        )
        outputs["session_id"] = session_id

        execute(
            """
            INSERT INTO rag.chat_outputs(
                session_id, run_id, urgency_band, visit_category, wait_p50_minutes, wait_p90_minutes,
                explanation, disclaimers_json, config_snapshot_hash, created_at
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                session_id,
                outputs["run_id"],
                outputs["urgency_band"],
                outputs["visit_category"],
                int(outputs["wait_p50_minutes"]),
                int(outputs["wait_p90_minutes"]),
                outputs["explanation"],
                json.dumps(outputs["disclaimers"], ensure_ascii=False),
                outputs["config_snapshot_hash"],
                _now_iso(),
            ),
        )
        execute(
            "UPDATE rag.patient_chat_sessions SET ended_at=%s WHERE session_id=%s",
            (_now_iso(), session_id),
        )
        self._upsert_public_output(session_id=session_id, outputs=outputs)
        self._mark_public_session_done(session_id=session_id)
        logger.info("RAG intake session finalized: session_id=%s patient_id=%s run_id=%s", session_id, patient_id, outputs["run_id"])
        return {
            "session_id": session_id,
            "urgency_band": outputs["urgency_band"],
            "visit_category": outputs["visit_category"],
            "wait_p50_minutes": int(outputs["wait_p50_minutes"]),
            "wait_p90_minutes": int(outputs["wait_p90_minutes"]),
            "explanation": outputs["explanation"],
            "disclaimers": outputs["disclaimers"],
            "run_id": outputs["run_id"],
        }

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

        cfg = load_clinics_config()
        configured_clinics = cfg.get("clinics", []) if isinstance(cfg, dict) else []
        clinics: list[dict[str, str]] = []
        for row in configured_clinics:
            if not isinstance(row, dict):
                continue
            clinic_id = str(row.get("id") or "").strip()
            clinic_name = str(row.get("name") or "").strip()
            city = str(row.get("address_or_city") or "").strip()
            if not clinic_id or not clinic_name:
                continue
            clinics.append({"id": clinic_id, "name": clinic_name, "city": city})

        if not clinics:
            return {"ok": False, "patients_seeded": 0, "clinics_seeded": 0, "notes": ["No clinics found in clinics.yaml"]}

        for clinic in clinics:
            execute(
                """
                INSERT INTO rag.clinics(clinic_id, clinic_name, city, timezone)
                VALUES(%s,%s,%s,%s)
                ON CONFLICT (clinic_id) DO UPDATE SET clinic_name=EXCLUDED.clinic_name, city=EXCLUDED.city
                """,
                (clinic["id"], clinic["name"], clinic["city"], "America/Toronto"),
            )
        for clinic in clinics:
            clinic_id = clinic["id"]
            execute("DELETE FROM rag.clinic_faqs WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_rules WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_hours_services WHERE clinic_id=%s", (clinic_id,))
            # Delete child chunks before parent documents to satisfy FK constraints.
            execute("DELETE FROM rag.clinic_document_chunks WHERE clinic_id=%s", (clinic_id,))
            execute("DELETE FROM rag.clinic_documents WHERE clinic_id=%s", (clinic_id,))

        for idx, clinic in enumerate(clinics, start=1):
            clinic_id = clinic["id"]
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
                    f"{clinic['name']} triage SOP",
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
            # Delete child rows before parent rows to satisfy FK constraints.
            execute("DELETE FROM rag.patient_context_chunks WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.clinical_notes WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.encounters WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.medications WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.allergies WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.problem_list WHERE patient_id=%s", (p_id,))
            execute("DELETE FROM rag.lab_summaries WHERE patient_id=%s", (p_id,))

            encounter_id = f"enc_{p_id}_1"
            clinic_id = clinics[(hash(p_id) % len(clinics))]["id"]
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

            patient_snippets = [
                ("encounter", encounter_id, "Follow-up for chronic condition monitoring."),
                ("medication", f"med_{p_id}_1", "Lisinopril 10mg daily"),
                ("allergy", f"alg_{p_id}_1", "Penicillin reaction: Rash"),
                ("clinical_note", f"note_{p_id}_1", "Patient reports occasional headaches; no red-flag neurological symptoms."),
                ("lab_summary", f"lab_{p_id}_1", "Lipid panel: LDL mildly elevated; recommend routine follow-up."),
            ]
            for order, (source_type, source_id, snippet) in enumerate(patient_snippets, start=1):
                chunk_id = f"pch_{p_id}_{order}"
                if pgvector_enabled():
                    vector_literal = to_vector_literal(embed_text(snippet))
                    execute(
                        """
                        INSERT INTO rag.patient_context_chunks(chunk_id, patient_id, source_type, source_id, chunk_text, chunk_order, embedding)
                        VALUES(%s,%s,%s,%s,%s,%s,%s::vector)
                        """,
                        (chunk_id, p_id, source_type, source_id, snippet, order, vector_literal),
                    )
                else:
                    execute(
                        """
                        INSERT INTO rag.patient_context_chunks(chunk_id, patient_id, source_type, source_id, chunk_text, chunk_order, embedding_text)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (chunk_id, p_id, source_type, source_id, snippet, order, snippet),
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

