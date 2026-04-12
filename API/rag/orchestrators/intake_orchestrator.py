import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from API.rag.model_adapters.registry import active_adapter, active_model
from API.rag.prompt_logging import log_constructed_prompt, log_llm_inference
from API.rag.prompts.intake_templates import (
    disclaimers_for_language,
    final_classification_prompts,
    normalize_language,
    next_turn_prompts,
)
from Chatbot.backend.app.core.settings import settings

LOCALIZED_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "safe_escalation": (
            "If this may be severe or an emergency, seek urgent in-person care or call local emergency services. "
            "If you can, ask someone nearby for help."
        ),
        "welcome_intro": "Welcome. I can help collect intake details for {clinic_name}.",
        "welcome_scope": "This chat is for pre-intake support before your visit. I will ask a few short questions for operational queue planning.",
        "welcome_question": "What brings you in today, in one or two sentences?",
        "finish_ready": "Thanks. I have enough information to generate operational results. Please tap 'Finish' to see them.",
        "finish_tap": "Thanks. Tap 'Finish' to see operational results.",
        "fallback_detail_question": "Could you share one more detail that would help queue planning today?",
        "llm_safety": "If this may be severe or an emergency, seek urgent in-person care or call local emergency services.",
        "high_risk_explanation": "High-risk indicators detected. Seek urgent in-person care.",
        "placeholder_explanation": "Operational summary based on your answers.",
    },
    "fr": {
        "safe_escalation": (
            "Si cela peut etre grave ou une urgence, consultez rapidement en personne ou appelez les services d'urgence locaux. "
            "Si possible, demandez de l'aide a une personne proche."
        ),
        "welcome_intro": "Bienvenue. Je peux vous aider a recueillir les details de pre-triage pour {clinic_name}.",
        "welcome_scope": "Ce clavardage sert au pre-triage avant votre visite. Je vais poser quelques courtes questions pour la planification operationnelle de la file.",
        "welcome_question": "Qu'est-ce qui vous amene aujourd'hui, en une ou deux phrases?",
        "finish_ready": "Merci. J'ai assez d'information pour generer les resultats operationnels. Veuillez appuyer sur 'Terminer' pour les voir.",
        "finish_tap": "Merci. Appuyez sur 'Terminer' pour voir les resultats operationnels.",
        "fallback_detail_question": "Pouvez-vous partager un detail de plus utile a la planification de la file aujourd'hui?",
        "llm_safety": "Si cela peut etre grave ou une urgence, consultez rapidement en personne ou appelez les services d'urgence locaux.",
        "high_risk_explanation": "Des signes de risque eleve ont ete detectes. Consultez rapidement en personne.",
        "placeholder_explanation": "Resume operationnel base sur vos reponses.",
    },
    "es": {
        "safe_escalation": (
            "Si esto puede ser grave o una emergencia, busque atencion presencial urgente o llame a los servicios de emergencia locales. "
            "Si puede, pida ayuda a alguien cercano."
        ),
        "welcome_intro": "Bienvenido. Puedo ayudarle a recopilar los detalles de pretriaje para {clinic_name}.",
        "welcome_scope": "Este chat sirve para el pretriaje antes de su visita. Haré algunas preguntas cortas para la planificacion operativa de la fila.",
        "welcome_question": "Qué le trae hoy, en una o dos frases?",
        "finish_ready": "Gracias. Tengo informacion suficiente para generar los resultados operativos. Toque 'Finalizar' para verlos.",
        "finish_tap": "Gracias. Toque 'Finalizar' para ver los resultados operativos.",
        "fallback_detail_question": "Podria compartir un detalle mas que ayude a la planificacion de la fila hoy?",
        "llm_safety": "Si esto puede ser grave o una emergencia, busque atencion presencial urgente o llame a los servicios de emergencia locales.",
        "high_risk_explanation": "Se detectaron indicadores de alto riesgo. Busque atencion presencial urgente.",
        "placeholder_explanation": "Resumen operativo basado en sus respuestas.",
    },
}

DELTA_REWRITE_BY_INTENT: dict[str, dict[str, str]] = {
    "en": {
        "allergy_history": "Any new allergies or reactions since your last update?",
        "medication_history": "Any new or changed medications since your last update?",
        "chronic_history": "Any new chronic conditions or diagnosis changes since your last update?",
    },
    "fr": {
        "allergy_history": "Avez-vous de nouvelles allergies ou reactions depuis votre derniere mise a jour?",
        "medication_history": "Avez-vous de nouveaux medicaments ou des changements depuis votre derniere mise a jour?",
        "chronic_history": "Y a-t-il de nouvelles conditions chroniques ou des changements de diagnostic depuis votre derniere mise a jour?",
    },
    "es": {
        "allergy_history": "Tiene alergias nuevas o reacciones desde su ultima actualizacion?",
        "medication_history": "Tiene medicamentos nuevos o cambios desde su ultima actualizacion?",
        "chronic_history": "Hay condiciones cronicas nuevas o cambios de diagnostico desde su ultima actualizacion?",
    },
}

SCRIPTED_INTAKE_QUESTIONS: dict[str, list[str]] = {
    "en": [
        "How long have these symptoms or concerns been going on?",
        "Is there an injury involved, such as a fall or cut?",
        "Any timing constraints today, like needing to leave by a certain hour?",
        "Are your symptoms getting better, worse, or staying about the same?",
    ],
    "fr": [
        "Depuis combien de temps ces symptomes ou preoccupations durent-ils?",
        "Y a-t-il une blessure en cause, comme une chute ou une coupure?",
        "Avez-vous des contraintes d'horaire aujourd'hui, par exemple devoir partir a une certaine heure?",
        "Vos symptomes s'ameliorent-ils, empirent-ils, ou restent-ils semblables?",
    ],
    "es": [
        "Cuanto tiempo llevan estos sintomas o preocupaciones?",
        "Hay una lesion involucrada, como una caida o un corte?",
        "Tiene restricciones de horario hoy, por ejemplo tener que irse a cierta hora?",
        "Sus sintomas estan mejorando, empeorando o siguen igual?",
    ],
}


def _msg(language: str, key: str) -> str:
    return LOCALIZED_MESSAGES[normalize_language(language)][key]


def _delta_rewrite(language: str, intent: str) -> str | None:
    return DELTA_REWRITE_BY_INTENT.get(normalize_language(language), {}).get(intent)


def _scripted_questions(language: str) -> list[str]:
    return SCRIPTED_INTAKE_QUESTIONS[normalize_language(language)]


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


def _normalize_for_match(content: str) -> str:
    lowered = re.sub(r"\s+", " ", (content or "").strip()).lower()
    return re.sub(r"[^a-z0-9 ?]", "", lowered)


def _classify_question_intent(question: str) -> str | None:
    q = _normalize_for_match(question)
    if not q:
        return None
    if "allerg" in q and any(
        phrase in q
        for phrase in (
            "known allerg",
            "any allerg",
            "do you have allerg",
            "what allerg",
            "allergy history",
        )
    ):
        return "allergy_history"
    if any(term in q for term in ("medication", "medications", "meds", "current meds")) and any(
        phrase in q
        for phrase in (
            "do you take",
            "are you taking",
            "what meds",
            "what medications",
            "current medication",
            "known medication",
            "medication history",
        )
    ):
        return "medication_history"
    if any(term in q for term in ("chronic", "medical condition", "diagnosed")) and any(
        phrase in q
        for phrase in (
            "known",
            "history",
            "do you have",
            "any",
            "list",
        )
    ):
        return "chronic_history"
    if "how long" in q or "since when" in q:
        return "duration"
    if "scale of 1 to 10" in q or "rate" in q:
        return "severity"
    return None


def _known_history_intents(patient_context: str | None) -> set[str]:
    if not patient_context:
        return set()
    normalized = patient_context.lower()
    known: set[str] = set()
    if "[allergy]" in normalized or "known_allergies_present=true" in normalized:
        known.add("allergy_history")
    if "[medication]" in normalized or "known_medications_present=true" in normalized:
        known.add("medication_history")
    if "known_chronic_conditions_present=true" in normalized or "chronic condition" in normalized:
        known.add("chronic_history")
    return known


def _assistant_already_asked_question(transcript: list[dict[str, Any]], question: str) -> bool:
    target = _normalize_for_match(question)
    if not target:
        return False
    for message in transcript:
        if str(message.get("role") or "").lower() != "assistant":
            continue
        asked = _normalize_for_match(str(message.get("content") or ""))
        if asked and asked == target:
            return True
    return False


def _intent_already_asked_and_answered(transcript: list[dict[str, Any]], intent: str) -> bool:
    for idx, message in enumerate(transcript):
        if str(message.get("role") or "").lower() != "assistant":
            continue
        asked_intent = _classify_question_intent(str(message.get("content") or ""))
        if asked_intent != intent:
            continue
        for later in transcript[idx + 1 :]:
            if str(later.get("role") or "").lower() == "user":
                return True
    return False


def _first_non_duplicate_scripted_question(transcript: list[dict[str, Any]], language: str) -> str:
    for candidate in _scripted_questions(language):
        if not _assistant_already_asked_question(transcript, candidate):
            return candidate
    return _msg(language, "fallback_detail_question")


def _apply_repetition_guard(
    *,
    next_question: str,
    transcript: list[dict[str, Any]],
    patient_context: str | None,
    language: str,
) -> str:
    question = (next_question or "").strip()
    if not question:
        return _first_non_duplicate_scripted_question(transcript, language)

    intent = _classify_question_intent(question)
    known_history = _known_history_intents(patient_context)

    if intent and intent in known_history:
        rewritten = _delta_rewrite(language, intent)
        if rewritten and not _assistant_already_asked_question(transcript, rewritten):
            return rewritten
        return _first_non_duplicate_scripted_question(transcript, language)

    if intent and _intent_already_asked_and_answered(transcript, intent):
        return _first_non_duplicate_scripted_question(transcript, language)

    if _assistant_already_asked_question(transcript, question):
        return _first_non_duplicate_scripted_question(transcript, language)

    return question


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
        "resume operationnel base sur vos reponses.",
        "resume operationnel base sur vos reponses",
        "resumen operativo basado en sus respuestas.",
        "resumen operativo basado en sus respuestas",
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
    language: str = "en",
) -> str:
    normalized_language = normalize_language(language)
    highlights = _extract_user_highlights(transcript)
    visit = (visit_category or "general").strip() or "general"
    urgency = (urgency_band or "medium").strip() or "medium"
    if normalized_language == "fr":
        if highlights:
            details = "; ".join(f'"{item}"' for item in highlights)
            return (
                f"Selon les details de votre pre-triage ({details}), nous avons prepare un resume de visite {visit} "
                f"avec une urgence operationnelle {urgency} pour la planification de la file."
            )
        return (
            f"Nous avons prepare un resume de visite {visit} avec une urgence operationnelle {urgency} "
            "pour la planification de la file selon votre pre-triage."
        )
    if normalized_language == "es":
        if highlights:
            details = "; ".join(f'"{item}"' for item in highlights)
            return (
                f"Con base en los detalles de su pretriaje ({details}), preparamos un resumen de visita {visit} "
                f"con urgencia operativa {urgency} para la planificacion de la fila."
            )
        return (
            f"Preparamos un resumen de visita {visit} con urgencia operativa {urgency} "
            "para la planificacion de la fila segun su pretriaje."
        )
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


def _safety_check(transcript_text: str, *, language: str = "en") -> dict[str, Any]:
    normalized_language = normalize_language(language)
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
        "safe_message": _msg(normalized_language, "safe_escalation") if hit else "",
        "disclaimers": disclaimers_for_language(normalized_language),
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

    def first_message(
        self,
        clinic: dict[str, Any],
        patient_context: str | None = None,
        language: str = "en",
    ) -> tuple[str, list[str]]:
        _ = patient_context
        normalized_language = normalize_language(language)
        msg = (
            _msg(normalized_language, "welcome_intro").format(clinic_name=clinic.get("name"))
            + "\n\n"
            + _msg(normalized_language, "welcome_scope")
            + "\n\n"
            + _msg(normalized_language, "welcome_question")
        )
        return msg, disclaimers_for_language(normalized_language)

    def _generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        session_id: str | None = None,
        clinic_id: str | None = None,
        patient_id: str | None = None,
        endpoint: str | None = None,
        retrieval_mode: str | None = None,
        user_query: str | None = None,
    ) -> dict[str, Any]:
        adapter = active_adapter()
        model = active_model()
        provider = str(settings.rag_model_provider or "").strip().lower()
        if provider == "openai_compatible":
            prompt_payload = json.dumps(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                ensure_ascii=False,
                indent=2,
            )
        else:
            prompt_payload = f"{system_prompt}\n\n{user_prompt}"
        log_constructed_prompt(
            session_id=session_id or "unknown_session",
            user_query=user_query or "",
            constructed_prompt=prompt_payload,
            clinic_id=clinic_id,
            patient_id=patient_id,
            model_name=model.model_name,
            provider=provider or None,
            endpoint=endpoint,
            retrieval_mode=retrieval_mode,
        )
        try:
            data = adapter.generate_structured(
                model_name=model.model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Exception:
            log_llm_inference(
                session_id=session_id or "unknown_session",
                user_query=user_query or "",
                clinic_id=clinic_id,
                patient_id=patient_id,
                model_name=model.model_name,
                provider=provider or None,
                endpoint=endpoint,
                retrieval_mode=retrieval_mode,
                inference_source="adapter_error",
            )
            raise

        if isinstance(data, dict):
            if any(key in data for key in ("decision", "urgency_band", "visit_category", "next_question")):
                log_llm_inference(
                    session_id=session_id or "unknown_session",
                    user_query=user_query or "",
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    model_name=model.model_name,
                    provider=provider or None,
                    endpoint=endpoint,
                    retrieval_mode=retrieval_mode,
                    inference_json=data,
                )
                return data
            nested = _extract_first_json_object(str(data.get("assistant_message") or ""))
            if nested:
                log_llm_inference(
                    session_id=session_id or "unknown_session",
                    user_query=user_query or "",
                    clinic_id=clinic_id,
                    patient_id=patient_id,
                    model_name=model.model_name,
                    provider=provider or None,
                    endpoint=endpoint,
                    retrieval_mode=retrieval_mode,
                    inference_json=nested,
                    inference_source="assistant_message_json",
                )
                return nested
        return {}

    def _log_fallback_inference(
        self,
        *,
        session_id: str | None,
        user_query: str,
        clinic_id: str | None,
        patient_id: str | None,
        endpoint: str | None,
        retrieval_mode: str | None,
        reason: str,
    ) -> None:
        provider = str(settings.rag_model_provider or "").strip().lower() or None
        model_name: str | None = None
        try:
            model_name = active_model().model_name
        except Exception:
            model_name = None
        log_llm_inference(
            session_id=session_id or "unknown_session",
            user_query=user_query,
            clinic_id=clinic_id,
            patient_id=patient_id,
            model_name=model_name,
            provider=provider,
            endpoint=endpoint,
            retrieval_mode=retrieval_mode,
            inference_source=reason,
        )

    def next_turn(
        self,
        *,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
        patient_context: str | None = None,
        language: str = "en",
        session_id: str | None = None,
        clinic_id: str | None = None,
        patient_id: str | None = None,
        endpoint: str | None = None,
        retrieval_mode: str | None = None,
    ) -> tuple[str, bool, dict[str, int]]:
        normalized_language = normalize_language(language)
        turn_count = sum(1 for message in transcript if str(message.get("role") or "").lower() == "user")
        transcript_text = transcript_to_text(transcript)
        latest_user_query = ""
        for message in reversed(transcript):
            if str(message.get("role") or "").lower() == "user":
                latest_user_query = str(message.get("content") or "")
                break

        safety = _safety_check(transcript_text, language=normalized_language)
        if safety["is_high_risk"]:
            self._log_fallback_inference(
                session_id=session_id,
                user_query=latest_user_query,
                clinic_id=clinic_id or str(clinic.get("id") or ""),
                patient_id=patient_id,
                endpoint=endpoint or "/rag/chat/turn",
                retrieval_mode=retrieval_mode,
                reason="safety_short_circuit",
            )
            return safety["safe_message"], True, {"turn_count": turn_count, "max_turns": self.max_turns}

        if turn_count >= self.max_turns:
            self._log_fallback_inference(
                session_id=session_id,
                user_query=latest_user_query,
                clinic_id=clinic_id or str(clinic.get("id") or ""),
                patient_id=patient_id,
                endpoint=endpoint or "/rag/chat/turn",
                retrieval_mode=retrieval_mode,
                reason="max_turns_reached",
            )
            return (
                _msg(normalized_language, "finish_ready"),
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
            language=normalized_language,
        )
        data: dict[str, Any] = {}
        try:
            data = self._generate_structured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                session_id=session_id,
                clinic_id=clinic_id or str(clinic.get("id") or ""),
                patient_id=patient_id,
                endpoint=endpoint or "/rag/chat/turn",
                retrieval_mode=retrieval_mode,
                user_query=latest_user_query,
            )
        except Exception:
            data = {}

        if not data:
            self._log_fallback_inference(
                session_id=session_id,
                user_query=latest_user_query,
                clinic_id=clinic_id or str(clinic.get("id") or ""),
                patient_id=patient_id,
                endpoint=endpoint or "/rag/chat/turn",
                retrieval_mode=retrieval_mode,
                reason="fallback_scripted",
            )
            scripted = _scripted_questions(normalized_language)
            idx = min(turn_count, len(scripted) - 1)
            next_q = scripted[idx]
            done = turn_count >= len(scripted)
            if done:
                return _msg(normalized_language, "finish_tap"), True, {
                    "turn_count": turn_count,
                    "max_turns": self.max_turns,
                }
            return next_q, False, {"turn_count": turn_count, "max_turns": self.max_turns}

        decision = str(data.get("decision", "ASK")).upper()
        if decision == "SAFETY":
            return (
                _msg(normalized_language, "llm_safety"),
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )
        if decision == "STOP":
            return (
                _msg(normalized_language, "finish_ready"),
                True,
                {"turn_count": turn_count, "max_turns": self.max_turns},
            )

        next_question = _apply_repetition_guard(
            next_question=str(data.get("next_question") or "").strip(),
            transcript=transcript,
            patient_context=patient_context,
            language=normalized_language,
        )
        return next_question, False, {"turn_count": turn_count, "max_turns": self.max_turns}

    def finalize(
        self,
        *,
        clinic: dict[str, Any],
        transcript: list[dict[str, Any]],
        patient_context: str | None = None,
        language: str = "en",
        session_id: str | None = None,
        clinic_id: str | None = None,
        patient_id: str | None = None,
        endpoint: str | None = None,
        retrieval_mode: str | None = None,
        user_query: str | None = None,
    ) -> dict[str, Any]:
        normalized_language = normalize_language(language)
        transcript_text = transcript_to_text(transcript)
        clinic_context = format_clinic_context(clinic)
        latest_user_query = user_query or ""
        if not latest_user_query:
            for message in reversed(transcript):
                if str(message.get("role") or "").lower() == "user":
                    latest_user_query = str(message.get("content") or "")
                    break

        safety = _safety_check(transcript_text, language=normalized_language)
        if safety["is_high_risk"]:
            self._log_fallback_inference(
                session_id=session_id,
                user_query=latest_user_query,
                clinic_id=clinic_id or str(clinic.get("id") or ""),
                patient_id=patient_id,
                endpoint=endpoint or "/rag/chat/end",
                retrieval_mode=retrieval_mode,
                reason="safety_short_circuit",
            )
            urgency_band = "high"
            visit_category = "urgent"
            explanation = _msg(normalized_language, "high_risk_explanation")
        else:
            system_prompt, user_prompt = final_classification_prompts(
                clinic_context=clinic_context,
                transcript=transcript_text,
                patient_context=patient_context,
                language=normalized_language,
            )
            try:
                data = self._generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    session_id=session_id,
                    clinic_id=clinic_id or str(clinic.get("id") or ""),
                    patient_id=patient_id,
                    endpoint=endpoint or "/rag/chat/end",
                    retrieval_mode=retrieval_mode,
                    user_query=user_query or "",
                )
            except Exception:
                data = {}
            if not data:
                self._log_fallback_inference(
                    session_id=session_id,
                    user_query=latest_user_query,
                    clinic_id=clinic_id or str(clinic.get("id") or ""),
                    patient_id=patient_id,
                    endpoint=endpoint or "/rag/chat/end",
                    retrieval_mode=retrieval_mode,
                    reason="fallback_finalize_default",
                )
            urgency_band = str(data.get("urgency_band", "medium")).lower()
            if urgency_band not in {"low", "medium", "high"}:
                urgency_band = "medium"
            visit_category = str(data.get("visit_category", "general")).strip() or "general"
            explanation = str(data.get("explanation", "")).strip() or _msg(normalized_language, "placeholder_explanation")
            if _is_placeholder_explanation(explanation):
                explanation = _build_explanation_from_transcript(
                    transcript=transcript,
                    visit_category=visit_category,
                    urgency_band=urgency_band,
                    language=normalized_language,
                )

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
            "disclaimers": disclaimers_for_language(normalized_language),
            "run_id": f"run_{secrets.token_hex(12)}",
            "config_snapshot_hash": clinic_snapshot_hash(clinic),
        }

