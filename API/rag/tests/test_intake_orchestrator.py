from API.rag.orchestrators.intake_orchestrator import RagIntakeOrchestrator


class _FakeModel:
    model_name = "local-test-model"


class _FakeAdapter:
    def __init__(self):
        self.calls: list[dict] = []

    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str):
        self.calls.append(
            {
                "model_name": model_name,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        if "Task: Decide the next best intake question OR decide to stop." in user_prompt:
            return {
                "decision": "ASK",
                "next_question": "When did this begin?",
                "reason": "Need symptom duration for operational triage.",
            }
        return {
            "urgency_band": "low",
            "visit_category": "general",
            "explanation": "Operational classification from local model using retrieved context.",
        }


def test_intake_orchestrator_uses_rag_adapter_for_turn_and_finalize(monkeypatch):
    adapter = _FakeAdapter()
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: adapter)
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())

    orchestrator = RagIntakeOrchestrator()
    clinic = {
        "id": "clinic_1",
        "name": "Clinic One",
        "address_or_city": "Kitchener",
        "hours": {"monday": "08:00-18:00"},
        "mock_capacity": {"servers_total": 3, "avg_service_minutes": 12},
    }
    transcript = [
        {"role": "assistant", "content": "Welcome. What brings you in today?"},
        {"role": "user", "content": "I have had a sore throat since yesterday."},
    ]

    assistant_message, done, progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context="- [medication] Lisinopril 10mg daily",
    )
    assert assistant_message == "When did this begin?"
    assert done is False
    assert progress["turn_count"] == 1

    outputs = orchestrator.finalize(
        clinic=clinic,
        transcript=transcript,
        patient_context="- [allergy] Penicillin reaction: Rash",
    )
    assert outputs["urgency_band"] == "low"
    assert outputs["visit_category"] == "general"
    assert outputs["wait_p50_minutes"] >= 0
    assert outputs["wait_p90_minutes"] >= outputs["wait_p50_minutes"]

    # Verify generation path is through RAG's local model adapter hook.
    assert len(adapter.calls) == 2
    assert all(call["model_name"] == "local-test-model" for call in adapter.calls)

