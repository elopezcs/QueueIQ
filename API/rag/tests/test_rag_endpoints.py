from fastapi.testclient import TestClient

from API.main import create_app


class _FakeService:
    def __init__(self):
        self.orchestrator = self
        self.last_preferred_language = None

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

    def start_session(self, *, patient_id: str, clinic_id: str, patient_profile=None, preferred_language: str | None = None):
        self.last_preferred_language = preferred_language
        return {
            "session_id": "sess_test",
            "assistant_message": "welcome",
            "disclaimers": ["not diagnosis"],
        }

    def turn(self, *, patient_id: str, session_id: str, user_message: str):
        return {
            "assistant_message": "answer",
            "done": False,
            "progress": {"turn_count": 2, "max_turns": 10},
        }

    def end(self, *, patient_id: str, session_id: str):
        return {
            "session_id": session_id,
            "urgency_band": "medium",
            "visit_category": "general",
            "wait_p50_minutes": 10,
            "wait_p90_minutes": 20,
            "explanation": "Operational summary.",
            "disclaimers": ["not diagnosis"],
            "run_id": "run_1",
        }

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

    def list_audit_sessions(
        self,
        *,
        requester_patient_id: str,
        requester_role: str,
        patient_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return [
            {
                "session_id": "sess_test",
                "patient_id": requester_patient_id,
                "clinic_id": "kitchener-downtown",
                "started_at": "2026-01-01T00:00:00+00:00",
                "ended_at": None,
                "turn_count": 2,
                "run_count": 2,
                "urgency_band": "medium",
                "visit_category": "general",
                "wait_p50_minutes": 10,
                "wait_p90_minutes": 20,
                "output_created_at": "2026-01-01T00:00:02+00:00",
            }
        ]

    def list_audit_turns(self, *, requester_patient_id: str, requester_role: str, session_id: str):
        return [
            {
                "turn_id": "turn_1",
                "session_id": session_id,
                "turn_index": 1,
                "route": "mixed",
                "status": "ok",
                "user_message": "hello",
                "assistant_message": "hi",
                "trace_id": "trace_1",
                "run_id": "run_1",
                "started_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:00:01+00:00",
                "latency_ms": 1000,
            }
        ]

    def list_audit_runs(
        self,
        *,
        requester_patient_id: str,
        requester_role: str,
        patient_id: str | None = None,
        session_id: str | None = None,
        model_key: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ):
        return [
            {
                "run_id": "run_1",
                "turn_id": "turn_1",
                "trace_id": "trace_1",
                "session_id": session_id or "sess_test",
                "model_key": "gemma3_4b",
                "model_name": "gemma3:4b",
                "provider": "ollama",
                "prompt_version": "gemma_v1",
                "status": "ok",
                "error_type": None,
                "error_message": None,
                "created_at": "2026-01-01T00:00:01+00:00",
            }
        ]

    def session_audit_timeline(self, *, requester_patient_id: str, requester_role: str, session_id: str):
        return {
            "session": {
                "session_id": session_id,
                "patient_id": requester_patient_id,
                "clinic_id": "kitchener-downtown",
                "started_at": "2026-01-01T00:00:00+00:00",
                "ended_at": None,
            },
            "turns": self.list_audit_turns(
                requester_patient_id=requester_patient_id,
                requester_role=requester_role,
                session_id=session_id,
            ),
            "llm_runs": self.list_audit_runs(
                requester_patient_id=requester_patient_id,
                requester_role=requester_role,
                session_id=session_id,
            ),
            "session_output": {
                "session_id": session_id,
                "run_id": "run_1",
                "urgency_band": "medium",
                "visit_category": "general",
                "wait_p50_minutes": 10,
                "wait_p90_minutes": 20,
                "explanation": "Operational summary.",
                "disclaimers_json": ["not diagnosis"],
                "config_snapshot_hash": "cfg_1",
                "created_at": "2026-01-01T00:00:02+00:00",
            },
        }


def _auth_header(client: TestClient, email: str) -> dict[str, str]:
    login = client.post("/auth/demo-login", json={"email": email})
    assert login.status_code == 200
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_rag_chat_start_turn_end(monkeypatch):
    fake_service = _FakeService()
    monkeypatch.setattr("API.rag.routes.get_rag_service", lambda: fake_service)
    client = TestClient(create_app())
    headers = _auth_header(client, "alice.patient@queueiq.local")

    start = client.post(
        "/rag/chat/start",
        json={"clinic_id": "kitchener-downtown", "preferred_language": "es"},
        headers=headers,
    )
    assert start.status_code == 200
    assert fake_service.last_preferred_language == "es"
    session_id = start.json()["session_id"]

    turn = client.post("/rag/chat/turn", json={"session_id": session_id, "user_message": "What are my clinic options?"}, headers=headers)
    assert turn.status_code == 200
    assert turn.json()["done"] is False
    assert turn.json()["progress"]["max_turns"] == 10

    end = client.post("/rag/chat/end", json={"session_id": session_id}, headers=headers)
    assert end.status_code == 200
    assert end.json()["urgency_band"] == "medium"


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


def test_rag_audit_endpoints(monkeypatch):
    monkeypatch.setattr("API.rag.routes.get_rag_service", lambda: _FakeService())
    client = TestClient(create_app())
    headers = _auth_header(client, "alice.patient@queueiq.local")

    sessions = client.get("/rag/audit/sessions", headers=headers)
    assert sessions.status_code == 200
    assert sessions.json()[0]["session_id"] == "sess_test"
    assert sessions.json()[0]["urgency_band"] == "medium"

    turns = client.get("/rag/audit/session/sess_test/turns", headers=headers)
    assert turns.status_code == 200
    assert turns.json()[0]["turn_id"] == "turn_1"

    runs = client.get("/rag/audit/runs?session_id=sess_test", headers=headers)
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "run_1"

    timeline = client.get("/rag/audit/session/sess_test/timeline", headers=headers)
    assert timeline.status_code == 200
    body = timeline.json()
    assert body["session"]["session_id"] == "sess_test"
    assert len(body["turns"]) == 1
    assert len(body["llm_runs"]) == 1
    assert body["session_output"]["session_id"] == "sess_test"
    assert body["session_output"]["urgency_band"] == "medium"

