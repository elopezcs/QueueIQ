import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "Chatbot" / "backend"))

from API.rag.services.rag_service import RagService


def _service_with_mocks(monkeypatch, *, raise_next_turn: bool = False):
    executed: list[tuple[str, tuple | list | None]] = []
    message_id = {"value": 0}

    def fake_execute(query, params=None):
        executed.append((str(query), params))

    def fake_fetch_all(query, params=None):
        text = str(query)
        if "FROM rag.patient_chat_sessions WHERE session_id=%s LIMIT 1" in text:
            return [
                {
                    "session_id": "sess_1",
                    "patient_id": "pat_1",
                    "clinic_id": "clinic_1",
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "ended_at": None,
                }
            ]
        if "SELECT 1 FROM rag.chat_outputs" in text:
            return []
        if "SELECT COALESCE(MAX(turn_index), 0) AS max_turn_index FROM rag.chat_turns" in text:
            return [{"max_turn_index": 0}]
        if "FROM rag.patient_chat_messages" in text:
            return [{"role": "user", "content": "headache"}]
        return []

    def fake_execute_fetch_one(query, params=None):
        text = str(query)
        if "INSERT INTO rag.patient_chat_messages" in text and "RETURNING id" in text:
            message_id["value"] += 1
            return {"id": message_id["value"]}
        return None

    monkeypatch.setattr("API.rag.services.rag_service.init_rag_db", lambda: (True, False))
    monkeypatch.setattr("API.rag.services.rag_service.persist_model_registry", lambda: None)
    monkeypatch.setattr("API.rag.services.rag_service.rag_db_enabled", lambda: False)
    monkeypatch.setattr("API.rag.services.rag_service.execute", fake_execute)
    monkeypatch.setattr("API.rag.services.rag_service.fetch_all", fake_fetch_all)
    monkeypatch.setattr("API.rag.services.rag_service.execute_fetch_one", fake_execute_fetch_one)
    monkeypatch.setattr(
        "API.rag.services.rag_service.active_model",
        lambda: SimpleNamespace(
            key="gemma3_4b",
            model_name="gemma3:4b",
            provider="ollama",
            prompt_variant="gemma",
        ),
    )
    monkeypatch.setattr(
        "API.rag.services.rag_service.get_clinic_by_id",
        lambda clinic_id: {
            "id": clinic_id,
            "name": "Clinic One",
            "address_or_city": "Toronto",
            "hours": {},
            "mock_capacity": {"servers_total": 3, "avg_service_minutes": 12},
        },
    )

    service = RagService()
    service.orchestrator.patient_retriever.retrieve = lambda **kwargs: []
    if raise_next_turn:
        service.intake_orchestrator.next_turn = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("llm down"))
    else:
        service.intake_orchestrator.next_turn = lambda **kwargs: ("next question", False, {"turn_count": 1, "max_turns": 10})
    return service, executed


def test_turn_persists_turn_trace_and_run(monkeypatch):
    service, executed = _service_with_mocks(monkeypatch)
    result = service.turn(patient_id="pat_1", session_id="sess_1", user_message="I need clinic hours")
    assert result["assistant_message"] == "next question"

    sql_text = "\n".join(item[0] for item in executed)
    assert "INSERT INTO rag.chat_turns" in sql_text
    assert "INSERT INTO rag.retrieval_traces" in sql_text
    assert "INSERT INTO rag.llm_runs" in sql_text
    assert "UPDATE rag.chat_turns" in sql_text


def test_turn_persists_error_run_when_llm_fails(monkeypatch):
    service, executed = _service_with_mocks(monkeypatch, raise_next_turn=True)
    result = service.turn(patient_id="pat_1", session_id="sess_1", user_message="I need clinic hours")
    assert "temporary processing issue" in result["assistant_message"]

    llm_writes = [row for row in executed if "INSERT INTO rag.llm_runs" in row[0]]
    assert llm_writes
    params = llm_writes[-1][1]
    assert params is not None
    assert "llm_error" in params
