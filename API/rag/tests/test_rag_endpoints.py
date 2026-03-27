from fastapi.testclient import TestClient

from API.rag.orchestrators.rag_orchestrator import RagTurnResult
from API.main import create_app


class _FakeService:
    def __init__(self):
        self.orchestrator = self

    def health(self):
        return {"status": "ok", "database_ready": True, "pgvector_enabled": False}

    def models(self):
        return [
            {
                "key": "gemma3_4b",
                "provider": "ollama",
                "model_name": "gemma3:4b",
                "prompt_variant": "gemma",
                "active": True,
            }
        ]

    def seed(self):
        return {"ok": True, "patients_seeded": 3, "clinics_seeded": 3, "notes": ["seeded"]}

    def start_session(self, *, patient_id: str, clinic_id: str, patient_profile=None):
        return {
            "session_id": "sess_test",
            "assistant_message": "welcome",
            "disclaimers": ["not diagnosis"],
        }

    def turn(self, *, patient_id: str, session_id: str, user_message: str):
        return RagTurnResult(
            assistant_message="answer",
            done=False,
            route="mixed",
            trace_id="trace_1",
            run_id="run_1",
            patient_context=[{"source_type": "encounter", "source_id": "e1", "snippet": "x"}],
            clinic_context=[{"source_type": "clinic_rule", "source_id": "r1", "snippet": "y"}],
        )

    def end(self, *, patient_id: str, session_id: str):
        return {"session_id": session_id, "ended": True, "final_summary": "done", "sources": []}

    def run_turn(self, *, session_id: str, patient_id: str, clinic_id: str, user_message: str):
        return self.turn(patient_id=patient_id, session_id=session_id, user_message=user_message)

    def retrieve_only(self, *, patient_id: str, clinic_id: str, user_message: str):
        return (
            "mixed",
            [{"source_type": "encounter", "source_id": "e1", "snippet": "x"}],
            [{"source_type": "clinic_rule", "source_id": "r1", "snippet": "y"}],
        )

    def session_detail(self, *, patient_id: str, session_id: str):
        return {"session_id": session_id, "patient_id": patient_id, "messages": []}

    def trace_detail(self, trace_id: str):
        return {"trace_id": trace_id, "patient_id": "demo-patient-alice"}


def _auth_header(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/demo-login", json={"email": email})
    assert login.status_code == 200
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_rag_chat_start_turn_end(monkeypatch):
    monkeypatch.setattr("API.rag.routes.get_rag_service", lambda: _FakeService())
    client = TestClient(create_app())
    headers = _auth_header(client, "alice.patient@queueiq.local")

    start = client.post("/rag/chat/start", json={"clinic_id": "kitchener-downtown"}, headers=headers)
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post("/rag/chat/turn", json={"session_id": session_id, "user_message": "What are my clinic options?"}, headers=headers)
    assert turn.status_code == 200
    assert turn.json()["route"] == "mixed"

    end = client.post("/rag/chat/end", json={"session_id": session_id}, headers=headers)
    assert end.status_code == 200
    assert end.json()["ended"] is True


def test_rag_seed_smoke(monkeypatch):
    monkeypatch.setattr("API.rag.routes.get_rag_service", lambda: _FakeService())
    client = TestClient(create_app())
    headers = _auth_header(client, "manager@queueiq.local")
    response = client.post("/rag/seed", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["patients_seeded"] >= 2


def test_rag_retrieve_debug(monkeypatch):
    monkeypatch.setattr("API.rag.routes.get_rag_service", lambda: _FakeService())
    client = TestClient(create_app())
    headers = _auth_header(client, "alice.patient@queueiq.local")
    response = client.post(
        "/rag/retrieve/debug",
        json={"clinic_id": "kitchener-downtown", "query": "clinic hours and my meds"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"] == "mixed"
    assert isinstance(data["patient_context"], list)
    assert isinstance(data["clinic_context"], list)

