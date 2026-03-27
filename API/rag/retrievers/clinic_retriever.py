from API.rag.db import fetch_all, pgvector_enabled, to_vector_literal
from API.rag.model_adapters.registry import embed_text


class ClinicKnowledgeRetriever:
    def _score(self, *, query: str, source_type: str, snippet: str) -> int:
        lowered = query.lower()
        score = 0
        if any(token in lowered for token in ("hour", "open", "close", "time", "when")):
            if source_type == "clinic_hours_service":
                score += 50
        if any(token in lowered for token in ("policy", "rule", "refill")):
            if source_type == "clinic_rule":
                score += 40
        if any(token in lowered for token in ("faq", "walk-in", "walk in")):
            if source_type == "clinic_faq":
                score += 30
        if source_type == "clinic_chunk":
            score += 10
        if source_type == "clinic_document":
            score += 8
        snippet_lower = snippet.lower()
        for token in (t for t in lowered.split() if len(t) > 2):
            if token in snippet_lower:
                score += 2
        return score

    def retrieve(
        self,
        *,
        clinic_id: str,
        query: str,
        doc_type: str | None = None,
        effective_date: str | None = None,
        limit: int = 8,
    ) -> list[dict]:
        merged: list[dict] = []

        hours = fetch_all(
            """
            SELECT id AS source_id, 'clinic_hours_service' AS source_type,
                   (day_of_week || ' ' || COALESCE(open_time,'') || '-' || COALESCE(close_time,'') || ' ' || service_name) AS snippet
            FROM rag.clinic_hours_services
            WHERE clinic_id = %s
            LIMIT %s
            """,
            (clinic_id, max(1, limit // 2)),
        )
        merged.extend(hours)

        if pgvector_enabled():
            try:
                query_vec = to_vector_literal(embed_text(query))
                chunk_rows = fetch_all(
                    """
                    SELECT chunk_id AS source_id, 'clinic_chunk' AS source_type, chunk_text AS snippet
                    FROM rag.clinic_document_chunks
                    WHERE clinic_id = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (clinic_id, query_vec, max(1, limit // 2)),
                )
                merged.extend(chunk_rows)
            except Exception:
                pass

        params: list = [clinic_id]
        clauses = ["clinic_id = %s"]
        if doc_type:
            clauses.append("doc_type = %s")
            params.append(doc_type)
        if effective_date:
            clauses.append("effective_date <= %s")
            params.append(effective_date)

        docs = fetch_all(
            (
                "SELECT document_id AS source_id, 'clinic_document' AS source_type, "
                "(title || ': ' || LEFT(body, 240)) AS snippet "
                f"FROM rag.clinic_documents WHERE {' AND '.join(clauses)} ORDER BY effective_date DESC NULLS LAST LIMIT %s"
            ),
            tuple(params + [max(1, limit // 2)]),
        )
        faqs = fetch_all(
            """
            SELECT faq_id AS source_id, 'clinic_faq' AS source_type,
                   (question || ' -> ' || answer) AS snippet
            FROM rag.clinic_faqs
            WHERE clinic_id = %s
            LIMIT %s
            """,
            (clinic_id, max(1, limit // 3)),
        )
        rules = fetch_all(
            """
            SELECT rule_id AS source_id, 'clinic_rule' AS source_type,
                   (rule_name || ': ' || rule_text) AS snippet
            FROM rag.clinic_rules
            WHERE clinic_id = %s
            LIMIT %s
            """,
            (clinic_id, max(1, limit // 3)),
        )
        merged.extend(docs + faqs + rules)

        if query.strip():
            tokens = [t.lower() for t in query.split() if len(t) > 2]
            if tokens:
                merged = [
                    row
                    for row in merged
                    if any(token in str(row.get("snippet", "")).lower() for token in tokens)
                ] or merged

        scored = sorted(
            merged,
            key=lambda row: self._score(
                query=query,
                source_type=str(row.get("source_type") or ""),
                snippet=str(row.get("snippet") or ""),
            ),
            reverse=True,
        )
        return [
            {
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "snippet": row["snippet"],
            }
            for row in scored[:limit]
        ]

