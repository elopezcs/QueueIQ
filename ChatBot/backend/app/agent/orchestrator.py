import json
import secrets
from typing import Any

from app.agent.llm_client import LLMClient
from app.agent.prompts import (
    DEFAULT_DISCLAIMERS,
    prompt_next_question,
    prompt_final_classification,
)
from app.agent.safety import SafetyGuard
from app.agent.queue_risk import mock_queue_snapshot, estimate_wait_minutes
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
    for m in transcript:
        role = m.get("role", "unknown")
        content = (m.get("content") or "").strip()
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines).strip()


class ChatOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.safety = SafetyGuard()
        self.max_turns = settings.max_turns

    def first_message(self, clinic: dict[str, Any]) -> tuple[str, list[str]]:
        msg = (
            f"Welcome. I can help collect intake details for {clinic.get('name')}." "\n\n"
            "I will ask a few short questions for operational queue planning. "
            "This is not a medical diagnosis." "\n\n"
            "What brings you in today, in one or two sentences?"
        )
        return msg, DEFAULT_DISCLAIMERS

    def next_turn(
        self,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
    ) -> tuple[str, bool, dict[str, int]]:
        # turn_count counts user turns (excluding assistant messages)
        turn_count = sum(1 for m in transcript if m.get("role") == "user")
        transcript_text = transcript_to_text(transcript)

        safety = self.safety.check(transcript_text)
        if safety["is_high_risk"]:
            return safety["safe_message"], True, {"turn_count": turn_count, "max_turns": self.max_turns}

        if turn_count >= self.max_turns:
            return (
                "Thanks. I have enough information to generate operational results. "
                "Please tap “Finish” to see them.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        clinic_context = format_clinic_context(clinic)

        if not self.llm.enabled:
            # Stub behavior: ask a short fixed sequence, then stop.
            scripted = [
                "How long have these symptoms or concerns been going on?",
                "Is there an injury involved, such as a fall or cut?",
                "Any constraints today, like needing to leave by a certain time?",
            ]
            idx = min(turn_count, len(scripted) - 1)
            next_q = scripted[idx]
            done = (turn_count >= len(scripted))
            return next_q if not done else "Thanks. Tap “Finish” to see operational results.", done, {
                "turn_count": turn_count,
                "max_turns": self.max_turns,
            }

        data = self.llm.generate_json(
            prompt_next_question(
                clinic_context=clinic_context,
                transcript=transcript_text,
                turn_count=turn_count,
                max_turns=self.max_turns,
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
                "Thanks. I have enough information to generate operational results. "
                "Please tap “Finish” to see them.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        next_question = (data.get("next_question") or "").strip()
        if not next_question:
            next_question = "Could you share a bit more detail about what you need help with today?"
        return next_question, False, {"turn_count": turn_count, "max_turns": self.max_turns}

    def finalize(self, clinic: dict[str, Any], transcript: list[dict[str, Any]]) -> dict[str, Any]:
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
            explanation = "Operational estimate based on the intake summary (stub mode)."
        else:
            data = self.llm.generate_json(prompt_final_classification(clinic_context, transcript_text))
            urgency_band = str(data.get("urgency_band", "medium")).lower()
            if urgency_band not in ["low", "medium", "high"]:
                urgency_band = "medium"
            visit_category = str(data.get("visit_category", "general")).strip() or "general"
            explanation = str(data.get("explanation", "")).strip() or "Operational summary based on your answers."

        capacity = clinic.get("mock_capacity", {})
        servers_total = int(capacity.get("servers_total", 3))
        avg_service_minutes = int(capacity.get("avg_service_minutes", 12))

        snap = mock_queue_snapshot(clinic_id=clinic.get("id", "unknown"), servers_total=servers_total)
        p50, p90 = estimate_wait_minutes(
            queue_length=int(snap["queue_length"]),
            servers_busy=int(snap["servers_busy"]),
            servers_total=int(snap["servers_total"]),
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
