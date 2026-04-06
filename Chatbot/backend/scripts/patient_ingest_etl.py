from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg2.extras import RealDictCursor

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from API.rag.db import get_conn, init_rag_db, to_vector_literal  # noqa: E402
from API.rag.model_adapters.registry import embed_text  # noqa: E402


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: object, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = value.strip()
    return cleaned if cleaned else fallback


def _stable_id(prefix: str, *parts: str) -> str:
    joined = "|".join(parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _payload_records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("patients"), list):
            return [item for item in payload["patients"] if isinstance(item, dict)]
        return [payload]
    return []


def _patient_obj(record: dict[str, Any]) -> dict[str, Any]:
    patient = record.get("patient")
    if isinstance(patient, dict):
        return patient
    return record


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    patient = _patient_obj(record)
    patient_id = _safe_text(patient.get("patient_id"))
    if not patient_id:
        source_key = _safe_text(patient.get("external_id")) or _safe_text(patient.get("email")) or _now_iso()
        patient_id = _stable_id("pat", source_key)
    full_name = _safe_text(patient.get("full_name"), patient_id)
    email = _safe_text(patient.get("email"), f"{patient_id}@queueiq.local").lower()
    role = _safe_text(patient.get("role"), "patient").lower()
    if role not in {"patient", "staff", "manager"}:
        role = "patient"
    clinic_id = _safe_text(patient.get("clinic_id")) or None
    date_of_birth = _safe_text(patient.get("date_of_birth")) or None
    sex = _safe_text(patient.get("sex")) or None
    medical_profile = patient.get("medical_profile")
    if not isinstance(medical_profile, dict):
        medical_profile = {}

    normalized = {
        "patient": {
            "patient_id": patient_id,
            "full_name": full_name,
            "email": email,
            "email_verified": bool(patient.get("email_verified")),
            "is_admin": bool(patient.get("is_admin")) or role == "manager",
            "role": role,
            "clinic_id": clinic_id if role == "staff" else None,
            "date_of_birth": date_of_birth,
            "sex": sex,
            "medical_profile": medical_profile,
        },
        "encounters": record.get("encounters") if isinstance(record.get("encounters"), list) else [],
        "medications": record.get("medications") if isinstance(record.get("medications"), list) else [],
        "allergies": record.get("allergies") if isinstance(record.get("allergies"), list) else [],
        "clinical_notes": record.get("clinical_notes") if isinstance(record.get("clinical_notes"), list) else [],
        "lab_summaries": record.get("lab_summaries") if isinstance(record.get("lab_summaries"), list) else [],
    }
    return normalized


def _upsert_public_patient(cur, patient: dict[str, Any], now_iso: str) -> None:
    medical_profile_json = json.dumps(patient.get("medical_profile") or {}, ensure_ascii=False)
    cur.execute(
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
              medical_profile_json=EXCLUDED.medical_profile_json,
              updated_at=EXCLUDED.updated_at
        """,
        (
            patient["patient_id"],
            patient["full_name"],
            patient["email"],
            1 if patient["email_verified"] else 0,
            1 if patient["is_admin"] else 0,
            patient["role"],
            patient["clinic_id"],
            None,
            medical_profile_json,
            None,
            now_iso,
            now_iso,
            None,
        ),
    )


def _upsert_rag_patient(cur, patient: dict[str, Any]) -> None:
    cur.execute(
        """
        INSERT INTO rag.patients(patient_id, full_name, date_of_birth, sex)
        VALUES(%s,%s,%s,%s)
        ON CONFLICT (patient_id) DO UPDATE
          SET full_name=EXCLUDED.full_name,
              date_of_birth=COALESCE(EXCLUDED.date_of_birth, rag.patients.date_of_birth),
              sex=COALESCE(EXCLUDED.sex, rag.patients.sex)
        """,
        (
            patient["patient_id"],
            patient["full_name"],
            patient["date_of_birth"],
            patient["sex"],
        ),
    )


def _upsert_encounters(cur, patient_id: str, encounters: list[dict[str, Any]]) -> int:
    written = 0
    for row in encounters:
        if not isinstance(row, dict):
            continue
        encounter_id = _safe_text(row.get("encounter_id"))
        if not encounter_id:
            encounter_id = _stable_id(
                "enc",
                patient_id,
                _safe_text(row.get("clinic_id")),
                _safe_text(row.get("encounter_type")),
                _safe_text(row.get("encounter_date")),
                _safe_text(row.get("summary")),
            )
        clinic_id = _safe_text(row.get("clinic_id"), "unknown-clinic")
        encounter_type = _safe_text(row.get("encounter_type"), "general")
        encounter_date = _safe_text(row.get("encounter_date"), _now_iso())
        summary = _safe_text(row.get("summary"), "No summary provided.")
        cur.execute(
            """
            INSERT INTO rag.encounters(encounter_id, patient_id, clinic_id, encounter_type, encounter_date, summary)
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT (encounter_id) DO UPDATE
              SET clinic_id=EXCLUDED.clinic_id,
                  encounter_type=EXCLUDED.encounter_type,
                  encounter_date=EXCLUDED.encounter_date,
                  summary=EXCLUDED.summary
            """,
            (encounter_id, patient_id, clinic_id, encounter_type, encounter_date, summary),
        )
        written += 1
    return written


def _upsert_medications(cur, patient_id: str, medications: list[dict[str, Any]]) -> int:
    written = 0
    for row in medications:
        if not isinstance(row, dict):
            continue
        medication_name = _safe_text(row.get("medication_name"))
        if not medication_name:
            continue
        medication_id = _safe_text(row.get("medication_id"))
        if not medication_id:
            medication_id = _stable_id(
                "med",
                patient_id,
                medication_name,
                _safe_text(row.get("dosage")),
                _safe_text(row.get("frequency")),
                _safe_text(row.get("start_date")),
            )
        cur.execute(
            """
            INSERT INTO rag.medications(
              medication_id, patient_id, medication_name, dosage, frequency, start_date, end_date, active
            )
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (medication_id) DO UPDATE
              SET medication_name=EXCLUDED.medication_name,
                  dosage=EXCLUDED.dosage,
                  frequency=EXCLUDED.frequency,
                  start_date=EXCLUDED.start_date,
                  end_date=EXCLUDED.end_date,
                  active=EXCLUDED.active
            """,
            (
                medication_id,
                patient_id,
                medication_name,
                _safe_text(row.get("dosage")) or None,
                _safe_text(row.get("frequency")) or None,
                _safe_text(row.get("start_date")) or None,
                _safe_text(row.get("end_date")) or None,
                bool(row.get("active", True)),
            ),
        )
        written += 1
    return written


def _upsert_allergies(cur, patient_id: str, allergies: list[dict[str, Any]]) -> int:
    written = 0
    for row in allergies:
        if not isinstance(row, dict):
            continue
        allergen = _safe_text(row.get("allergen"))
        if not allergen:
            continue
        allergy_id = _safe_text(row.get("allergy_id"))
        if not allergy_id:
            allergy_id = _stable_id("alg", patient_id, allergen, _safe_text(row.get("severity")))
        cur.execute(
            """
            INSERT INTO rag.allergies(allergy_id, patient_id, allergen, reaction, severity, active)
            VALUES(%s,%s,%s,%s,%s,%s)
            ON CONFLICT (allergy_id) DO UPDATE
              SET allergen=EXCLUDED.allergen,
                  reaction=EXCLUDED.reaction,
                  severity=EXCLUDED.severity,
                  active=EXCLUDED.active
            """,
            (
                allergy_id,
                patient_id,
                allergen,
                _safe_text(row.get("reaction")) or None,
                _safe_text(row.get("severity")) or None,
                bool(row.get("active", True)),
            ),
        )
        written += 1
    return written


def _upsert_notes(cur, patient_id: str, notes: list[dict[str, Any]]) -> int:
    written = 0
    for row in notes:
        if not isinstance(row, dict):
            continue
        content = _safe_text(row.get("content"))
        if not content:
            continue
        note_id = _safe_text(row.get("note_id"))
        if not note_id:
            note_id = _stable_id("note", patient_id, _safe_text(row.get("note_type")), content[:80])
        cur.execute(
            """
            INSERT INTO rag.clinical_notes(note_id, patient_id, encounter_id, note_type, content, created_at)
            VALUES(%s,%s,%s,%s,%s,COALESCE(%s::timestamptz, NOW()))
            ON CONFLICT (note_id) DO UPDATE
              SET encounter_id=EXCLUDED.encounter_id,
                  note_type=EXCLUDED.note_type,
                  content=EXCLUDED.content,
                  created_at=EXCLUDED.created_at
            """,
            (
                note_id,
                patient_id,
                _safe_text(row.get("encounter_id")) or None,
                _safe_text(row.get("note_type"), "clinical_note"),
                content,
                _safe_text(row.get("created_at")) or None,
            ),
        )
        written += 1
    return written


def _upsert_labs(cur, patient_id: str, labs: list[dict[str, Any]]) -> int:
    written = 0
    for row in labs:
        if not isinstance(row, dict):
            continue
        test_name = _safe_text(row.get("test_name"))
        summary = _safe_text(row.get("summary"))
        if not test_name or not summary:
            continue
        lab_summary_id = _safe_text(row.get("lab_summary_id"))
        if not lab_summary_id:
            lab_summary_id = _stable_id("lab", patient_id, test_name, summary[:80], _safe_text(row.get("test_date")))
        cur.execute(
            """
            INSERT INTO rag.lab_summaries(lab_summary_id, patient_id, test_name, summary, test_date)
            VALUES(%s,%s,%s,%s,%s)
            ON CONFLICT (lab_summary_id) DO UPDATE
              SET test_name=EXCLUDED.test_name,
                  summary=EXCLUDED.summary,
                  test_date=EXCLUDED.test_date
            """,
            (
                lab_summary_id,
                patient_id,
                test_name,
                summary,
                _safe_text(row.get("test_date"), _now_iso()),
            ),
        )
        written += 1
    return written


def _snippets_from_db(cur, patient_id: str) -> list[tuple[str, str, str]]:
    snippets: list[tuple[str, str, str]] = []
    cur.execute(
        """
        SELECT encounter_id, summary
        FROM rag.encounters
        WHERE patient_id=%s
        ORDER BY encounter_date DESC
        """,
        (patient_id,),
    )
    for row in cur.fetchall():
        snippets.append(("encounter", str(row["encounter_id"]), _safe_text(row["summary"])))

    cur.execute(
        """
        SELECT medication_id, medication_name, dosage, frequency
        FROM rag.medications
        WHERE patient_id=%s AND active=TRUE
        """,
        (patient_id,),
    )
    for row in cur.fetchall():
        chunk = " ".join(
            [
                _safe_text(row["medication_name"]),
                _safe_text(row.get("dosage")),
                _safe_text(row.get("frequency")),
            ]
        ).strip()
        if chunk:
            snippets.append(("medication", str(row["medication_id"]), chunk))

    cur.execute(
        """
        SELECT allergy_id, allergen, reaction
        FROM rag.allergies
        WHERE patient_id=%s AND active=TRUE
        """,
        (patient_id,),
    )
    for row in cur.fetchall():
        chunk = f"{_safe_text(row['allergen'])} reaction: {_safe_text(row.get('reaction'), 'unknown')}"
        snippets.append(("allergy", str(row["allergy_id"]), chunk))

    cur.execute(
        """
        SELECT note_id, content
        FROM rag.clinical_notes
        WHERE patient_id=%s
        ORDER BY created_at DESC
        """,
        (patient_id,),
    )
    for row in cur.fetchall():
        content = _safe_text(row["content"])
        if content:
            snippets.append(("clinical_note", str(row["note_id"]), content[:1200]))

    cur.execute(
        """
        SELECT lab_summary_id, test_name, summary
        FROM rag.lab_summaries
        WHERE patient_id=%s
        ORDER BY test_date DESC
        """,
        (patient_id,),
    )
    for row in cur.fetchall():
        chunk = f"{_safe_text(row['test_name'])}: {_safe_text(row['summary'])}"
        snippets.append(("lab_summary", str(row["lab_summary_id"]), chunk))
    return snippets


def _rebuild_patient_chunks(cur, patient_id: str, use_vector: bool) -> int:
    cur.execute("DELETE FROM rag.patient_context_chunks WHERE patient_id=%s", (patient_id,))
    snippets = _snippets_from_db(cur, patient_id)
    written = 0
    for idx, (source_type, source_id, chunk_text) in enumerate(snippets, start=1):
        if not chunk_text:
            continue
        chunk_id = _stable_id("pch", patient_id, source_type, source_id, str(idx))
        if use_vector:
            vector_literal = to_vector_literal(embed_text(chunk_text))
            cur.execute(
                """
                INSERT INTO rag.patient_context_chunks(
                  chunk_id, patient_id, source_type, source_id, chunk_text, chunk_order, embedding
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s::vector)
                ON CONFLICT (chunk_id) DO UPDATE
                  SET chunk_text=EXCLUDED.chunk_text,
                      chunk_order=EXCLUDED.chunk_order,
                      embedding=EXCLUDED.embedding
                """,
                (chunk_id, patient_id, source_type, source_id, chunk_text, idx, vector_literal),
            )
        else:
            cur.execute(
                """
                INSERT INTO rag.patient_context_chunks(
                  chunk_id, patient_id, source_type, source_id, chunk_text, chunk_order, embedding_text
                )
                VALUES(%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (chunk_id) DO UPDATE
                  SET chunk_text=EXCLUDED.chunk_text,
                      chunk_order=EXCLUDED.chunk_order,
                      embedding_text=EXCLUDED.embedding_text
                """,
                (chunk_id, patient_id, source_type, source_id, chunk_text, idx, chunk_text),
            )
        written += 1
    return written


def _validate_patient(cur, patient_id: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    checks = {
        "public_patients": "SELECT COUNT(*) AS n FROM patients WHERE patient_id=%s",
        "rag_patients": "SELECT COUNT(*) AS n FROM rag.patients WHERE patient_id=%s",
        "encounters": "SELECT COUNT(*) AS n FROM rag.encounters WHERE patient_id=%s",
        "medications": "SELECT COUNT(*) AS n FROM rag.medications WHERE patient_id=%s",
        "allergies": "SELECT COUNT(*) AS n FROM rag.allergies WHERE patient_id=%s",
        "clinical_notes": "SELECT COUNT(*) AS n FROM rag.clinical_notes WHERE patient_id=%s",
        "lab_summaries": "SELECT COUNT(*) AS n FROM rag.lab_summaries WHERE patient_id=%s",
        "patient_context_chunks": "SELECT COUNT(*) AS n FROM rag.patient_context_chunks WHERE patient_id=%s",
    }
    for key, sql in checks.items():
        cur.execute(sql, (patient_id,))
        row = cur.fetchone()
        counts[key] = int(row["n"] if row else 0)

    cur.execute(
        """
        SELECT COALESCE(COUNT(DISTINCT source_type), 0) AS n
        FROM rag.patient_context_chunks
        WHERE patient_id=%s
        """,
        (patient_id,),
    )
    distinct_sources = int(cur.fetchone()["n"])

    return {
        "patient_id": patient_id,
        "counts": counts,
        "chunk_source_types": distinct_sources,
        "ok": counts["public_patients"] == 1 and counts["rag_patients"] == 1,
    }


def _ingest_one(cur, record: dict[str, Any], use_vector: bool, skip_chunks: bool) -> dict[str, Any]:
    normalized = _normalize_record(record)
    patient = normalized["patient"]
    patient_id = str(patient["patient_id"])
    now_iso = _now_iso()

    _upsert_public_patient(cur, patient, now_iso)
    _upsert_rag_patient(cur, patient)

    encounter_count = _upsert_encounters(cur, patient_id, normalized["encounters"])
    medication_count = _upsert_medications(cur, patient_id, normalized["medications"])
    allergy_count = _upsert_allergies(cur, patient_id, normalized["allergies"])
    note_count = _upsert_notes(cur, patient_id, normalized["clinical_notes"])
    lab_count = _upsert_labs(cur, patient_id, normalized["lab_summaries"])

    chunk_count = 0
    if not skip_chunks:
        chunk_count = _rebuild_patient_chunks(cur, patient_id, use_vector=use_vector)

    validation = _validate_patient(cur, patient_id)
    return {
        "patient_id": patient_id,
        "written": {
            "encounters": encounter_count,
            "medications": medication_count,
            "allergies": allergy_count,
            "clinical_notes": note_count,
            "lab_summaries": lab_count,
            "patient_context_chunks": chunk_count,
        },
        "validation": validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk ingest patient history into patients + rag.* tables.")
    parser.add_argument("--input", required=True, help="Path to JSON payload with one or more patient records.")
    parser.add_argument("--patient-id", default=None, help="Optional filter to ingest a single patient_id from batch.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of records to process.")
    parser.add_argument("--skip-chunks", action="store_true", help="Skip rebuild of rag.patient_context_chunks.")
    parser.add_argument("--dry-run", action="store_true", help="Execute and validate, then rollback transaction.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue processing next record after an error.")
    args = parser.parse_args()

    payload_path = Path(args.input).resolve()
    if not payload_path.exists():
        raise SystemExit(f"Input file not found: {payload_path}")

    raw_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    records = _payload_records(raw_payload)
    if not records:
        raise SystemExit("No ingest records found. Expected a dict/list with patient data.")

    if args.patient_id:
        records = [r for r in records if _normalize_record(r)["patient"]["patient_id"] == args.patient_id]
    if args.limit and args.limit > 0:
        records = records[: args.limit]
    if not records:
        raise SystemExit("No records matched the provided filters.")

    db_ready, has_vector = init_rag_db()
    if not db_ready:
        raise SystemExit("RAG database is not enabled. Configure DATABASE_URL or RAG_DATABASE_URL.")

    summary: dict[str, Any] = {
        "input": str(payload_path),
        "records_requested": len(records),
        "dry_run": bool(args.dry_run),
        "skip_chunks": bool(args.skip_chunks),
        "vector_enabled": bool(has_vector),
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "results": [],
        "errors": [],
    }

    with get_conn() as conn:
        for record in records:
            patient_id = _normalize_record(record)["patient"]["patient_id"]
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    result = _ingest_one(cur, record, use_vector=has_vector, skip_chunks=args.skip_chunks)
                if args.dry_run:
                    conn.rollback()
                else:
                    conn.commit()
                summary["processed"] += 1
                summary["succeeded"] += 1
                summary["results"].append(result)
                print(json.dumps({"patient_id": patient_id, "status": "ok"}, ensure_ascii=False), flush=True)
            except Exception as exc:
                conn.rollback()
                summary["processed"] += 1
                summary["failed"] += 1
                summary["errors"].append({"patient_id": patient_id, "error": str(exc)})
                print(json.dumps({"patient_id": patient_id, "status": "error", "error": str(exc)}, ensure_ascii=False), flush=True)
                if not args.continue_on_error:
                    break

    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
