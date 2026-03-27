from API.rag.db import fetch_all


class PatientContextRetriever:
    def retrieve(
        self,
        *,
        patient_id: str,
        query: str,
        date_from: str | None = None,
        source_type: str | None = None,
        encounter_type: str | None = None,
        limit: int = 8,
    ) -> list[dict]:
        params: list = [patient_id]
        clauses = ["patient_id = %s"]
        if date_from:
            clauses.append("encounter_date >= %s")
            params.append(date_from)
        if encounter_type:
            clauses.append("encounter_type = %s")
            params.append(encounter_type)
        encounter_sql = (
            "SELECT encounter_id AS source_id, 'encounter' AS source_type, summary AS snippet, encounter_date AS sort_at "
            f"FROM rag.encounters WHERE {' AND '.join(clauses)} ORDER BY encounter_date DESC LIMIT {max(1, limit // 2)}"
        )

        meds = fetch_all(
            """
            SELECT medication_id AS source_id, 'medication' AS source_type,
                   (medication_name || ' ' || COALESCE(dosage,'') || ' ' || COALESCE(frequency,'')) AS snippet,
                   NOW() AS sort_at
            FROM rag.medications
            WHERE patient_id = %s AND active = TRUE
            LIMIT %s
            """,
            (patient_id, max(1, limit // 4)),
        )
        allergies = fetch_all(
            """
            SELECT allergy_id AS source_id, 'allergy' AS source_type,
                   (allergen || ' reaction: ' || COALESCE(reaction, 'unknown')) AS snippet,
                   NOW() AS sort_at
            FROM rag.allergies
            WHERE patient_id = %s AND active = TRUE
            LIMIT %s
            """,
            (patient_id, max(1, limit // 4)),
        )
        notes = fetch_all(
            """
            SELECT note_id AS source_id, 'clinical_note' AS source_type, LEFT(content, 260) AS snippet, created_at AS sort_at
            FROM rag.clinical_notes
            WHERE patient_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (patient_id, max(1, limit // 4)),
        )
        labs = fetch_all(
            """
            SELECT lab_summary_id AS source_id, 'lab_summary' AS source_type,
                   (test_name || ': ' || summary) AS snippet, test_date AS sort_at
            FROM rag.lab_summaries
            WHERE patient_id = %s
            ORDER BY test_date DESC
            LIMIT %s
            """,
            (patient_id, max(1, limit // 4)),
        )
        rows = fetch_all(encounter_sql, tuple(params))
        merged = rows + meds + allergies + notes + labs
        if source_type:
            merged = [row for row in merged if str(row.get("source_type")) == source_type]
        if query.strip():
            tokens = [t.lower() for t in query.split() if len(t) > 2]
            if tokens:
                merged = [
                    row
                    for row in merged
                    if any(token in str(row.get("snippet", "")).lower() for token in tokens)
                ] or merged
        return [{"source_id": row["source_id"], "source_type": row["source_type"], "snippet": row["snippet"]} for row in merged[:limit]]

