from API.rag.guardrails.rules import apply_guardrails


def test_guardrails_emergency_escalation():
    result = apply_guardrails("I have severe chest pain and cannot breathe", context_item_count=3)
    assert result.blocked is True
    assert result.done is True
    assert result.reason == "emergency_escalation"


def test_guardrails_diagnosis_block():
    result = apply_guardrails("Can you diagnose what condition I have?", context_item_count=3)
    assert result.blocked is True
    assert result.done is False
    assert result.reason == "diagnosis_request"


def test_guardrails_insufficient_context():
    result = apply_guardrails("What should I do next?", context_item_count=0)
    assert result.blocked is True
    assert result.reason == "insufficient_context"

