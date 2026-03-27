import re
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailResult:
    blocked: bool
    done: bool
    reason: str | None
    assistant_message: str | None


_EMERGENCY_PATTERNS = [
    r"\b(chest pain|can't breathe|cannot breathe|stroke|seizure|unconscious|severe bleeding)\b",
]
_DIAGNOSIS_PATTERNS = [r"\bdiagnos(e|is)|what condition do i have\b"]
_TREATMENT_PATTERNS = [r"\btreatment|therapy|care plan\b"]
_MEDICATION_PATTERNS = [r"\bmedication|prescribe|dosage|antibiotic|painkiller\b"]


def _matches_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def apply_guardrails(user_message: str, context_item_count: int) -> GuardrailResult:
    if _matches_any(user_message, _EMERGENCY_PATTERNS):
        return GuardrailResult(
            blocked=True,
            done=True,
            reason="emergency_escalation",
            assistant_message=(
                "Your message may indicate an emergency. Please call local emergency services "
                "or seek urgent in-person care now."
            ),
        )
    if _matches_any(user_message, _DIAGNOSIS_PATTERNS):
        return GuardrailResult(
            blocked=True,
            done=False,
            reason="diagnosis_request",
            assistant_message="I cannot provide a diagnosis. I can share clinic guidance and next steps.",
        )
    if _matches_any(user_message, _TREATMENT_PATTERNS):
        return GuardrailResult(
            blocked=True,
            done=False,
            reason="treatment_request",
            assistant_message="I cannot provide treatment advice. Please consult a licensed clinician.",
        )
    if _matches_any(user_message, _MEDICATION_PATTERNS):
        return GuardrailResult(
            blocked=True,
            done=False,
            reason="medication_request",
            assistant_message="I cannot recommend medications or dosage. Please consult your care team.",
        )
    if context_item_count <= 0:
        return GuardrailResult(
            blocked=True,
            done=False,
            reason="insufficient_context",
            assistant_message=(
                "I do not have enough context to answer safely. Please provide more detail "
                "or ask your clinic directly."
            ),
        )
    return GuardrailResult(blocked=False, done=False, reason=None, assistant_message=None)

