from typing import Any
from app.agent.llm_client import LLMClient
from app.agent.prompts import prompt_safety_guardrail, DEFAULT_DISCLAIMERS

DEFAULT_SAFE_ESCALATION = (
    "If this may be severe or an emergency, seek urgent in-person care or call local emergency services. "
    "If you can, ask someone nearby for help."
)


class SafetyGuard:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def check(self, transcript_text: str) -> dict[str, Any]:
        # If LLM disabled, do a simple keyword heuristic.
        if not self.llm.enabled:
            lowered = transcript_text.lower()
            keywords = [
                "chest pain",
                "trouble breathing",
                "cannot breathe",
                "severe bleeding",
                "fainted",
                "stroke",
                "suicidal",
                "overdose",
                "anaphylaxis",
            ]
            hit = any(k in lowered for k in keywords)
            return {
                "is_high_risk": hit,
                "safe_message": DEFAULT_SAFE_ESCALATION if hit else "",
                "disclaimers": DEFAULT_DISCLAIMERS,
            }

        data = self.llm.generate_json(prompt_safety_guardrail(transcript_text))
        is_high_risk = bool(data.get("is_high_risk", False))
        safe_message = str(data.get("safe_message") or DEFAULT_SAFE_ESCALATION) if is_high_risk else ""
        return {
            "is_high_risk": is_high_risk,
            "safe_message": safe_message,
            "disclaimers": DEFAULT_DISCLAIMERS,
        }
