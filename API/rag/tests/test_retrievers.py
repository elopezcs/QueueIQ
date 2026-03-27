from API.rag.retrievers.clinic_retriever import ClinicKnowledgeRetriever
from API.rag.retrievers.patient_retriever import PatientContextRetriever


def test_patient_retriever_scoped_to_patient(monkeypatch):
    def fake_fetch_all(query, params=None):
        text = str(query)
        if "rag.medications" in text:
            return [{"source_id": "med_1", "source_type": "medication", "snippet": "Lisinopril daily", "sort_at": "now"}]
        if "rag.allergies" in text:
            return [{"source_id": "alg_1", "source_type": "allergy", "snippet": "Penicillin rash", "sort_at": "now"}]
        return [{"source_id": "enc_1", "source_type": "encounter", "snippet": "Follow-up note", "sort_at": "now"}]

    monkeypatch.setattr("API.rag.retrievers.patient_retriever.fetch_all", fake_fetch_all)
    items = PatientContextRetriever().retrieve(patient_id="pat_1", query="medication follow-up")
    assert items
    assert all("source_id" in item for item in items)
    assert all(item["source_type"] in {"encounter", "medication", "allergy"} for item in items)


def test_clinic_retriever_returns_faq_rule_docs(monkeypatch):
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.pgvector_enabled", lambda: False)

    def fake_fetch_all(query, params=None):
        text = str(query)
        if "rag.clinic_faqs" in text:
            return [{"source_id": "faq_1", "source_type": "clinic_faq", "snippet": "Walk-ins accepted"}]
        if "rag.clinic_rules" in text:
            return [{"source_id": "rule_1", "source_type": "clinic_rule", "snippet": "Escalate emergency symptoms"}]
        return [{"source_id": "doc_1", "source_type": "clinic_document", "snippet": "SOP summary"}]

    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.fetch_all", fake_fetch_all)
    items = ClinicKnowledgeRetriever().retrieve(clinic_id="clinic_1", query="policy")
    assert items
    types = {item["source_type"] for item in items}
    assert {"clinic_document", "clinic_faq", "clinic_rule"} <= types


def test_clinic_retriever_prefers_vector_chunks_when_available(monkeypatch):
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.pgvector_enabled", lambda: True)
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.embed_text", lambda _: [0.1, 0.2, 0.3])
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.to_vector_literal", lambda _: "[0.1,0.2,0.3]")

    def fake_fetch_all(query, params=None):
        text = str(query)
        if "rag.clinic_document_chunks" in text:
            return [{"source_id": "chunk_1", "source_type": "clinic_chunk", "snippet": "nearest chunk"}]
        return []

    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.fetch_all", fake_fetch_all)
    items = ClinicKnowledgeRetriever().retrieve(clinic_id="clinic_1", query="hours")
    assert items[0]["source_type"] == "clinic_chunk"


def test_clinic_retriever_prioritizes_hours_for_hours_query(monkeypatch):
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.pgvector_enabled", lambda: True)
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.embed_text", lambda _: [0.1, 0.2, 0.3])
    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.to_vector_literal", lambda _: "[0.1,0.2,0.3]")

    def fake_fetch_all(query, params=None):
        text = str(query)
        if "rag.clinic_hours_services" in text:
            return [
                {
                    "source_id": "hours_1",
                    "source_type": "clinic_hours_service",
                    "snippet": "Monday-Friday 08:00-18:00 Primary care",
                }
            ]
        if "rag.clinic_document_chunks" in text:
            return [{"source_id": "chunk_1", "source_type": "clinic_chunk", "snippet": "Walk-in arrivals are accepted."}]
        return []

    monkeypatch.setattr("API.rag.retrievers.clinic_retriever.fetch_all", fake_fetch_all)
    items = ClinicKnowledgeRetriever().retrieve(clinic_id="clinic_1", query="What are clinic hours?")
    assert items
    assert items[0]["source_type"] == "clinic_hours_service"

