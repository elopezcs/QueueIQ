import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from API.rag.model_adapters.registry import active_adapter, active_model
from API.rag.prompts.intake_templates import (
    DEFAULT_DISCLAIMERS,
    final_classification_prompts,
    next_turn_prompts,
)
from Chatbot.backend.app.core.settings import settings

DEFAULT_SAFE_ESCALATION = (
    "If this may be severe or an emergency, seek urgent in-person care or call local emergency services. "
    "If you can, ask someone nearby for help."
)


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


def _extract_first_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _safety_check(transcript_text: str) -> dict[str, Any]:
    lowered = transcript_text.lower()
    keywords = [
        "chest pain",
        "trouble breathing",
        "cannot breathe",
        "can't breathe",
        "severe bleeding",
        "fainted",
        "stroke",
        "suicidal",
        "overdose",
        "anaphylaxis",
        "seizure",
        "unconscious",
    ]
    hit = any(k in lowered for k in keywords)
    return {
        "is_high_risk": hit,
        "safe_message": DEFAULT_SAFE_ESCALATION if hit else "",
        "disclaimers": DEFAULT_DISCLAIMERS,
    }


def mock_queue_snapshot(clinic_id: str, servers_total: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    bucket = now.strftime("%Y%m%d%H")
    seed = int(hashlib.sha256(f"{clinic_id}:{bucket}".encode("utf-8")).hexdigest(), 16)

    queue_length = seed % 18  # 0..17
    servers_busy = min(servers_total, 1 + (seed % (servers_total + 1)))
    return {
        "queue_length": int(queue_length),
        "servers_busy": int(servers_busy),
        "servers_total": int(servers_total),
        "updated_at": now.isoformat(),
    }


def estimate_wait_minutes(queue_length: int, servers_busy: int, servers_total: int, avg_service_minutes: int) -> tuple[int, int]:
    effective_servers = max(1, servers_total - max(0, servers_busy - 1))
    base = (queue_length / effective_servers) * max(5, avg_service_minutes)
    p50 = int(round(base))
    p90 = int(round(max(p50 + 10, base * 1.7)))
    return max(0, p50), max(0, p90)


def clinic_snapshot_hash(clinic: dict[str, Any]) -> str:
    raw = json.dumps(clinic, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RagIntakeOrchestrator:
    def __init__(self) -> None:
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

    def _generate_structured(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        adapter = active_adapter()
        model = active_model()
        data = adapter.generate_structured(
            model_name=model.model_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if isinstance(data, dict):
            if any(key in data for key in ("decision", "urgency_band", "visit_category", "next_question")):
                return data
            nested = _extract_first_json_object(str(data.get("assistant_message") or ""))
            if nested:
                return nested
        return {}

    def next_turn(
        self,
        *,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
        patient_context: str | None = None,
    ) -> tuple[str, bool, dict[str, int]]:
        turn_count = sum(1 for message in transcript if str(message.get("role") or "").lower() == "user")
        transcript_text = transcript_to_text(transcript)

        safety = _safety_check(transcript_text)
        if safety["is_high_risk"]:
            return safety["safe_message"], True, {"turn_count": turn_count, "max_turns": self.max_turns}

        if turn_count >= self.max_turns:
            return (
                "Thanks. I have enough information to generate operational results. Please tap 'Finish' to see them.",
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        clinic_context = format_clinic_context(clinic)
        system_prompt, user_prompt = next_turn_prompts(
            clinic_context=clinic_context,
            transcript=transcript_text,
            turn_count=turn_count,
            max_turns=self.max_turns,
            patient_context=patient_context,
        )
        data: dict[str, Any] = {}
        try:
            data = self._generate_structured(system_prompt=system_prompt, user_prompt=user_prompt)
        except Exception:
            data = {}

        if not data:
            scripted = [
                "How long have these symptoms or concerns been going on?",
                "Is there an injury involved, such as a fall or cut?",
                "Any timing constraints today, like needing to leave by a certain hour?",
            ]
            idx = min(turn_count, len(scripted) - 1)
            next_q = scripted[idx]
            done = turn_count >= len(scripted)
            if done:
                return "Thanks. Tap 'Finish' to see operational results.", True, {
                    "turn_count": turn_count,
                    "max_turns": self.max_turns,
                }
            return next_q, False, {"turn_count": turn_count, "max_turns": self.max_turns}

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

        next_question = str(data.get("next_question") or "").strip()
        if not next_question:
            next_question = "Could you share a bit more detail about what you need help with today?"
        return next_question, False, {"turn_count": turn_count, "max_turns": self.max_turns}

    def finalize(
        self,
        *,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
        patient_context: str | None = None,
    ) -> dict[str, Any]:
        transcript_text = transcript_to_text(transcript)
        clinic_context = format_clinic_context(clinic)

        safety = _safety_check(transcript_text)
        if safety["is_high_risk"]:
            urgency_band = "high"
            visit_category = "urgent"
            explanation = "High-risk indicators detected. Seek urgent in-person care."
        else:
            system_prompt, user_prompt = final_classification_prompts(
                clinic_context=clinic_context,
                transcript=transcript_text,
                patient_context=patient_context,
            )
            try:
                data = self._generate_structured(system_prompt=system_prompt, user_prompt=user_prompt)
            except Exception:
                data = {}
            urgency_band = str(data.get("urgency_band", "medium")).lower()
            if urgency_band not in {"low", "medium", "high"}:
                urgency_band = "medium"
            visit_category = str(data.get("visit_category", "general")).strip() or "general"
            explanation = str(data.get("explanation", "")).strip() or "Operational summary based on your answers."

        capacity = clinic.get("mock_capacity", {})
        servers_total = int(capacity.get("servers_total", 3))
        avg_service_minutes = int(capacity.get("avg_service_minutes", 12))

        snapshot = mock_queue_snapshot(clinic_id=str(clinic.get("id", "unknown")), servers_total=servers_total)
        p50, p90 = estimate_wait_minutes(
            queue_length=int(snapshot["queue_length"]),
            servers_busy=int(snapshot["servers_busy"]),
            servers_total=int(snapshot["servers_total"]),
            avg_service_minutes=avg_service_minutes,
        )

        return {
            "session_id": "unknown",
            "urgency_band": urgency_band,
            "visit_category": visit_category,
            "wait_p50_minutes": p50,
            "wait_p90_minutes": p90,
            "explanation": explanation,
            "disclaimers": DEFAULT_DISCLAIMERS,
            "run_id": f"run_{secrets.token_hex(12)}",
            "config_snapshot_hash": clinic_snapshot_hash(clinic),
        }

