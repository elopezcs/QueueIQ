from API.rag.db import fetch_all, pgvector_enabled, to_vector_literal
from API.rag.model_adapters.registry import embed_text


class PatientContextRetriever:
    def _retrieve_lexical(
        self,
        *,
        patient_id: str,
        query: str,
        date_from: str | None,
        source_type: str | None,
        encounter_type: str | None,
        limit: int,
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
        return [
            {"source_id": row["source_id"], "source_type": row["source_type"], "snippet": row["snippet"]}
            for row in merged[:limit]
        ]

    def _retrieve_vector(
        self,
        *,
        patient_id: str,
        query: str,
        source_type: str | None,
        limit: int,
    ) -> list[dict]:
        if not query.strip() or not pgvector_enabled():
            return []
        try:
            query_vec = to_vector_literal(embed_text(query))
            params: list = [patient_id]
            source_clause = ""
            if source_type:
                source_clause = "AND source_type = %s"
                params.append(source_type)
            params.extend([query_vec, max(1, limit)])
            rows = fetch_all(
                f"""
                SELECT source_id, source_type, chunk_text AS snippet
                FROM rag.patient_context_chunks
                WHERE patient_id = %s {source_clause}
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                tuple(params),
            )
            return [
                {"source_id": row["source_id"], "source_type": row["source_type"], "snippet": row["snippet"]}
                for row in rows
            ]
        except Exception:
            return []

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
        vector_items = self._retrieve_vector(
            patient_id=patient_id,
            query=query,
            source_type=source_type,
            limit=limit,
        )
        lexical_items = self._retrieve_lexical(
            patient_id=patient_id,
            query=query,
            date_from=date_from,
            source_type=source_type,
            encounter_type=encounter_type,
            limit=limit,
        )

        ordered: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for row in vector_items + lexical_items:
            key = (str(row.get("source_type") or ""), str(row.get("source_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(row)
            if len(ordered) >= limit:
                break
        return ordered

