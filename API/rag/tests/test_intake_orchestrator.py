from API.rag.orchestrators.intake_orchestrator import RagIntakeOrchestrator
from API.rag.prompts.intake_templates import next_turn_prompts


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


class _ErrorAdapter:
    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str):
        raise RuntimeError("adapter failure")


class _KnownAllergyQuestionAdapter:
    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str):
        _ = model_name, system_prompt, user_prompt
        return {
            "decision": "ASK",
            "next_question": "Do you have any known allergies?",
            "reason": "Need allergy history.",
        }


class _RepeatedDurationQuestionAdapter:
    def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str):
        _ = model_name, system_prompt, user_prompt
        return {
            "decision": "ASK",
            "next_question": "How long have these symptoms or concerns been going on?",
            "reason": "Need duration.",
        }


def test_first_message_is_concise_and_clinic_named():
    orchestrator = RagIntakeOrchestrator()
    clinic = {"name": "Walk-in Cambridge Hespeler"}
    message_with_context, disclaimers = orchestrator.first_message(
        clinic=clinic,
        patient_context="- [medication] Lisinopril 10mg daily",
    )
    message_without_context, _ = orchestrator.first_message(
        clinic=clinic,
        patient_context=None,
    )

    assert message_with_context == message_without_context
    assert "Walk-in Cambridge Hespeler" in message_with_context
    assert "pre-intake support" in message_with_context
    assert "What brings you in today" in message_with_context
    assert "profile and visit details already saved on your account" not in message_with_context
    assert isinstance(disclaimers, list) and disclaimers


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


def test_intake_orchestrator_logs_inference_payloads(monkeypatch):
    adapter = _FakeAdapter()
    prompt_logs: list[dict] = []
    inference_logs: list[dict] = []
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: adapter)
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_constructed_prompt",
        lambda **kwargs: prompt_logs.append(kwargs),
    )
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_llm_inference",
        lambda **kwargs: inference_logs.append(kwargs),
    )

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

    orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context="- [medication] Lisinopril 10mg daily",
        session_id="rag_sess_test",
        clinic_id="clinic_1",
        patient_id="pat_1",
        endpoint="/rag/chat/turn",
        retrieval_mode="patient",
    )
    orchestrator.finalize(
        clinic=clinic,
        transcript=transcript,
        patient_context="- [allergy] Penicillin reaction: Rash",
        session_id="rag_sess_test",
        clinic_id="clinic_1",
        patient_id="pat_1",
        endpoint="/rag/chat/end",
        retrieval_mode="finalize",
        user_query="Finish",
    )

    assert len(prompt_logs) == 2
    assert len(inference_logs) == 2
    assert inference_logs[0]["inference_json"]["decision"] == "ASK"
    assert inference_logs[0]["inference_json"]["next_question"] == "When did this begin?"
    assert inference_logs[1]["inference_json"]["urgency_band"] == "low"
    assert inference_logs[1]["inference_json"]["visit_category"] == "general"


def test_intake_orchestrator_logs_fallback_reasons_on_adapter_error(monkeypatch):
    inference_logs: list[dict] = []
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: _ErrorAdapter())
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_constructed_prompt",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_llm_inference",
        lambda **kwargs: inference_logs.append(kwargs),
    )

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
        {"role": "user", "content": "Headache"},
    ]

    message, done, _progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context=None,
        session_id="rag_sess_test",
        clinic_id="clinic_1",
        patient_id="pat_1",
        endpoint="/rag/chat/turn",
        retrieval_mode="patient",
    )
    outputs = orchestrator.finalize(
        clinic=clinic,
        transcript=transcript,
        patient_context=None,
        session_id="rag_sess_test",
        clinic_id="clinic_1",
        patient_id="pat_1",
        endpoint="/rag/chat/end",
        retrieval_mode="finalize",
        user_query="Finish",
    )

    reasons = [entry.get("inference_source") for entry in inference_logs]
    assert "adapter_error" in reasons
    assert "fallback_scripted" in reasons
    assert "fallback_finalize_default" in reasons
    assert isinstance(message, str) and message
    assert done is False
    assert outputs["urgency_band"] in {"low", "medium", "high"}


def test_prompt_includes_no_redundant_history_constraints():
    _system_prompt, user_prompt = next_turn_prompts(
        clinic_context='{"clinic_id":"clinic_1"}',
        transcript="ASSISTANT: Welcome\nUSER: Rash",
        turn_count=1,
        max_turns=10,
        patient_context="- [allergy] Penicillin reaction: Rash",
    )
    assert "Do NOT re-ask known chart facts" in user_prompt
    assert "Any new allergies or reactions since your last update?" in user_prompt


def test_prompt_includes_language_instruction_for_french():
    system_prompt, _user_prompt = next_turn_prompts(
        clinic_context='{"clinic_id":"clinic_1"}',
        transcript="ASSISTANT: Bonjour\nUSER: Douleur a la gorge",
        turn_count=1,
        max_turns=10,
        patient_context="- [allergy] Penicillin reaction: Rash",
        language="fr",
    )
    assert "Generate all user-facing strings in French." in system_prompt


def test_prompt_includes_language_instruction_for_spanish():
    system_prompt, _user_prompt = next_turn_prompts(
        clinic_context='{"clinic_id":"clinic_1"}',
        transcript="ASSISTANT: Hola\nUSER: Dolor de garganta",
        turn_count=1,
        max_turns=10,
        patient_context="- [allergy] Penicillin reaction: Rash",
        language="es",
    )
    assert "Generate all user-facing strings in Spanish." in system_prompt


def test_first_message_and_disclaimers_localize_for_french():
    orchestrator = RagIntakeOrchestrator()
    clinic = {"name": "Clinique Test"}
    message, disclaimers = orchestrator.first_message(clinic=clinic, language="fr")
    assert "Bienvenue." in message
    assert "pre-triage" in message
    assert isinstance(disclaimers, list) and disclaimers
    assert "Ce clavardage sert au pre-triage avant les visites en clinique." in disclaimers


def test_first_message_and_disclaimers_localize_for_spanish():
    orchestrator = RagIntakeOrchestrator()
    clinic = {"name": "Clinica Test"}
    message, disclaimers = orchestrator.first_message(clinic=clinic, language="es")
    assert "Bienvenido." in message
    assert "pretriaje" in message
    assert isinstance(disclaimers, list) and disclaimers
    assert "Este chat sirve para el pretriaje antes de las visitas en la clinica." in disclaimers


def test_finalize_fallback_explanation_localizes_for_spanish(monkeypatch):
    class _SpanishPlaceholderFinalizeAdapter:
        def generate_structured(self, *, model_name: str, system_prompt: str, user_prompt: str):
            _ = model_name, system_prompt, user_prompt
            return {
                "urgency_band": "medium",
                "visit_category": "general",
                "explanation": "Resumen operativo basado en sus respuestas.",
            }

    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: _SpanishPlaceholderFinalizeAdapter())
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
        {"role": "assistant", "content": "Bienvenido. Que le trae hoy?"},
        {"role": "user", "content": "Tengo tos y dolor de garganta desde ayer."},
    ]
    outputs = orchestrator.finalize(
        clinic=clinic,
        transcript=transcript,
        patient_context=None,
        language="es",
    )
    assert outputs["visit_category"] == "general"
    assert outputs["urgency_band"] == "medium"
    assert "Con base en los detalles de su pretriaje" in outputs["explanation"]


def test_known_allergy_question_is_rewritten_to_delta(monkeypatch):
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: _KnownAllergyQuestionAdapter())
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_constructed_prompt",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_llm_inference",
        lambda **kwargs: None,
    )

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
        {"role": "user", "content": "Rash on my arms."},
    ]

    message, done, _progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context="- [allergy] Penicillin reaction: Rash",
    )
    assert done is False
    assert message == "Any new allergies or reactions since your last update?"


def test_allergy_question_allowed_when_no_allergy_context(monkeypatch):
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: _KnownAllergyQuestionAdapter())
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_constructed_prompt",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_llm_inference",
        lambda **kwargs: None,
    )

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
        {"role": "user", "content": "Rash on my arms."},
    ]

    message, done, _progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context=None,
    )
    assert done is False
    assert message == "Do you have any known allergies?"


def test_repeated_intent_question_is_suppressed_after_user_answer(monkeypatch):
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_adapter", lambda: _RepeatedDurationQuestionAdapter())
    monkeypatch.setattr("API.rag.orchestrators.intake_orchestrator.active_model", lambda: _FakeModel())
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_constructed_prompt",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "API.rag.orchestrators.intake_orchestrator.log_llm_inference",
        lambda **kwargs: None,
    )

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
        {"role": "user", "content": "Rash."},
        {"role": "assistant", "content": "How long have these symptoms or concerns been going on?"},
        {"role": "user", "content": "Since this morning."},
    ]

    message, done, _progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=transcript,
        patient_context=None,
    )
    assert done is False
    assert message == "Is there an injury involved, such as a fall or cut?"

