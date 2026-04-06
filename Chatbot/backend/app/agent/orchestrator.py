import json
import re
import secrets
from typing import Any

from app.agent.llm_client import LLMClient
from app.agent.prompts import (
    DEFAULT_DISCLAIMERS,
    prompt_final_classification,
    prompt_next_question,
)
from app.agent.queue_risk import estimate_wait_minutes, mock_queue_snapshot
from app.agent.safety import SafetyGuard
from app.config.loader import clinic_config_snapshot_hash
from app.core.settings import settings


def format_clinic_context(clinic: dict[str, Any]) -> str:
    hours = clinic.get("hours", {})
    capacity = clinic.get("mock_capacity", {})
    return json.dumps(
        {
            "clinic_id": clinic.get("id"),
            "name": clinic.get("name"),
            "address_or_city": clinic.get("address_or_city"),
            "hours": hours,
            "mock_capacity": capacity,
        },
        ensure_ascii=False,
    )


def transcript_to_text(transcript: list[dict[str, Any]]) -> str:
    lines = []
    for message in transcript:
        role = message.get("role", "unknown")
        content = (message.get("content") or "").strip()
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines).strip()




def _normalize_message_text(content: str, *, max_length: int = 120) -> str:
    normalized = re.sub(r"\s+", " ", (content or "").strip())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max(0, max_length - 3)].rstrip() + "..."


def _extract_user_highlights(transcript: list[dict[str, Any]], *, max_items: int = 3) -> list[str]:
    highlights: list[str] = []
    seen: set[str] = set()
    for message in transcript:
        role = str(message.get("role") or "").lower()
        if role != "user":
            continue
        snippet = _normalize_message_text(str(message.get("content") or ""))
        if not snippet:
            continue
        key = snippet.lower()
        if key in seen:
            continue
        seen.add(key)
        highlights.append(snippet)
    if len(highlights) <= max_items:
        return highlights
    return highlights[-max_items:]


def _is_placeholder_explanation(explanation: str) -> bool:
    normalized = re.sub(r"\s+", " ", (explanation or "").strip()).lower()
    if not normalized:
        return True
    placeholders = {
        "operational summary based on your answers.",
        "operational summary based on your answers",
        "operational estimate based on your intake answers and any saved profile details available in stub mode.",
    }
    if normalized in placeholders:
        return True
    if normalized.startswith("operational summary based on your answers"):
        return True
    return len(normalized) < 40


def _build_explanation_from_transcript(
    *,
    transcript: list[dict[str, Any]],
    visit_category: str,
    urgency_band: str,
) -> str:
    highlights = _extract_user_highlights(transcript)
    visit = (visit_category or "general").strip() or "general"
    urgency = (urgency_band or "medium").strip() or "medium"
    if highlights:
        details = "; ".join(f'"{item}"' for item in highlights)
        return (
            f"Based on your intake details ({details}), we prepared a {visit} visit summary "
            f"with {urgency} operational urgency for queue planning."
        )
    return (
        f"We prepared a {visit} visit summary with {urgency} operational urgency "
        "for queue planning based on your intake."
    )


class ChatOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.safety = SafetyGuard()
        self.max_turns = settings.max_turns

    def first_message(self, clinic: dict[str, Any], patient_context: str | None = None) -> tuple[str, list[str]]:
        personalized_note = (
            "\n\nI can also use the profile and visit details already saved on your account to avoid repeating background questions."
            if patient_context
            else ""
        )
        msg = (
            f"Welcome. I can help collect intake details for {clinic.get('name')}."
            "\n\nI will ask a few short questions for operational queue planning. "
            "This is not a medical diagnosis."
            f"{personalized_note}"
            "\n\nWhat brings you in today, in one or two sentences?"
        )
        return msg, DEFAULT_DISCLAIMERS

    def next_turn(
        self,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
        patient_context: str | None = None,
    ) -> tuple[str, bool, dict[str, int]]:
        turn_count = sum(1 for message in transcript if message.get("role") == "user")
        transcript_text = transcript_to_text(transcript)

        safety = self.safety.check(transcript_text)
        if safety["is_high_risk"]:
            return safety["safe_message"], True, {"turn_count": turn_count, "max_turns": self.max_turns}

        if turn_count >= self.max_turns:
            return (
                "Thanks. I have enough information to generate operational results. Please tap 'Finish' to see them.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        clinic_context = format_clinic_context(clinic)

        if not self.llm.enabled:
            scripted = [
                "How long have these symptoms or concerns been going on?",
                "Is there an injury involved, such as a fall or cut?",
                "Any timing constraints today, like needing to leave by a certain hour?",
            ]
            idx = min(turn_count, len(scripted) - 1)
            next_q = scripted[idx]
            done = turn_count >= len(scripted)
            return next_q if not done else "Thanks. Tap 'Finish' to see operational results.", done, {
                "turn_count": turn_count,
                "max_turns": self.max_turns,
            }

        data = self.llm.generate_json(
            prompt_next_question(
                clinic_context=clinic_context,
                transcript=transcript_text,
                turn_count=turn_count,
                max_turns=self.max_turns,
                patient_context=patient_context,
            )
        )

        decision = str(data.get("decision", "ASK")).upper()
        if decision == "SAFETY":
            return (
                "If this may be severe or an emergency, seek urgent in-person care or call local emergency services.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        if decision == "STOP":
            return (
                "Thanks. I have enough information to generate operational results. Please tap 'Finish' to see them.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        next_question = (data.get("next_question") or "").strip()
        if not next_question:
            next_question = "Could you share a bit more detail about what you need help with today?"
        return next_question, False, {"turn_count": turn_count, "max_turns": self.max_turns}

    def finalize(self, clinic: dict[str, Any], transcript: list[dict[str, Any]], patient_context: str | None = None) -> dict[str, Any]:
        transcript_text = transcript_to_text(transcript)
        clinic_context = format_clinic_context(clinic)

        safety = self.safety.check(transcript_text)
        if safety["is_high_risk"]:
            urgency_band = "high"
            visit_category = "urgent"
            explanation = "High-risk indicators detected. Seek urgent in-person care."
        elif not self.llm.enabled:
            urgency_band = "medium"
            visit_category = "general"
            explanation = "Operational estimate based on your intake answers and any saved profile details available in stub mode."
        else:
            data = self.llm.generate_json(
                prompt_final_classification(clinic_context, transcript_text, patient_context=patient_context)
            )
            urgency_band = str(data.get("urgency_band", "medium")).lower()
            if urgency_band not in ["low", "medium", "high"]:
                urgency_band = "medium"
            visit_category = str(data.get("visit_category", "general")).strip() or "general"
            explanation = str(data.get("explanation", "")).strip() or "Operational summary based on your answers."
            if _is_placeholder_explanation(explanation):
                explanation = _build_explanation_from_transcript(
                    transcript=transcript,
                    visit_category=visit_category,
                    urgency_band=urgency_band,
                )

        capacity = clinic.get("mock_capacity", {})
        servers_total = int(capacity.get("servers_total", 3))
        avg_service_minutes = int(capacity.get("avg_service_minutes", 12))

        snapshot = mock_queue_snapshot(clinic_id=clinic.get("id", "unknown"), servers_total=servers_total)
        p50, p90 = estimate_wait_minutes(
            queue_length=int(snapshot["queue_length"]),
            servers_busy=int(snapshot["servers_busy"]),
            servers_total=int(snapshot["servers_total"]),
            avg_service_minutes=avg_service_minutes,
        )

        run_id = f"run_{secrets.token_hex(12)}"
        cfg_hash = clinic_config_snapshot_hash(clinic)

        return {
            "session_id": "unknown",
            "urgency_band": urgency_band,
            "visit_category": visit_category,
            "wait_p50_minutes": p50,
            "wait_p90_minutes": p90,
            "explanation": explanation,
            "disclaimers": DEFAULT_DISCLAIMERS,
            "run_id": run_id,
            "config_snapshot_hash": cfg_hash,
        }
