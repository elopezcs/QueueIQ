SYSTEM_POLICY = """You are ArrivalSignal for a clinic queue management system.
You MUST follow these rules:
- Scope is pre-intake chat only: collect concise operational intake details before a clinic visit.
- Provide operational outputs only. No diagnosis, no treatment, no medication advice.
- Ask short, neutral intake questions to support operational triage for queue planning.
- If the user asks out-of-scope questions (general medical Q&A, treatment planning, unrelated admin, casual chat),
  briefly redirect them back to pre-intake collection and continue with one intake question.
- If user describes severe symptoms or emergency indicators, stop and provide safe escalation guidance.
- Keep it under ~10 turns total unless explicitly extended by the system.
"""

LANGUAGE_INSTRUCTION = (
    "- Generate all user-facing strings in {language_name}.\n"
    "- Keep JSON keys exactly as requested in the schema.\n"
    "- Do not translate field names or enum values."
)

_DISCLAIMERS_BY_LANGUAGE = {
    "en": [
        "This chat is for pre-intake support before clinic visits.",
        "This tool provides operational guidance only. It is not a medical diagnosis.",
        "If you think this is an emergency or severe, seek urgent in-person care or call local emergency services.",
        "Wait-time estimates are not guaranteed and may change.",
    ],
    "fr": [
        "Ce clavardage sert au pre-triage avant les visites en clinique.",
        "Cet outil fournit uniquement des conseils operationnels. Ce n'est pas un diagnostic medical.",
        "Si vous pensez qu'il s'agit d'une urgence ou d'un cas grave, consultez rapidement en personne ou appelez les services d'urgence locaux.",
        "Les estimations de temps d'attente ne sont pas garanties et peuvent changer.",
    ],
    "es": [
        "Este chat sirve para el pretriaje antes de las visitas en la clinica.",
        "Esta herramienta solo ofrece orientacion operativa. No es un diagnostico medico.",
        "Si cree que se trata de una emergencia o algo grave, busque atencion presencial urgente o llame a los servicios de emergencia locales.",
        "Las estimaciones de tiempo de espera no estan garantizadas y pueden cambiar.",
    ],
}

DEFAULT_DISCLAIMERS = _DISCLAIMERS_BY_LANGUAGE["en"]


def normalize_language(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    return normalized if normalized in {"en", "fr", "es"} else "en"


def language_name(language: str) -> str:
    normalized = normalize_language(language)
    if normalized == "fr":
        return "French"
    if normalized == "es":
        return "Spanish"
    return "English"


def disclaimers_for_language(language: str | None) -> list[str]:
    normalized = normalize_language(language)
    return list(_DISCLAIMERS_BY_LANGUAGE[normalized])


def _patient_context_block(patient_context: str | None) -> str:
    if not patient_context:
        return "Known patient context:\nNone provided."
    return f"Known patient context:\n{patient_context}"


def next_turn_prompts(
    *,
    clinic_context: str,
    transcript: str,
    turn_count: int,
    max_turns: int,
    patient_context: str | None = None,
    language: str = "en",
) -> tuple[str, str]:
    normalized_language = normalize_language(language)
    language_rule = LANGUAGE_INSTRUCTION.format(language_name=language_name(normalized_language))
    system_prompt = (
        f"{SYSTEM_POLICY}\n"
        f"{language_rule}\n"
        "Return JSON only. Never return markdown fences."
    )
    user_prompt = (
        "Task: Decide the next best intake question OR decide to stop.\n\n"
        "Constraints:\n"
        "- No diagnosis, no treatment, no medical instructions.\n"
        "- Keep responses in pre-intake scope only.\n"
        "- For out-of-scope requests, briefly redirect to pre-intake and ask the next intake question.\n"
        "- Ask ONE question at a time.\n"
        "- If enough info has been collected, output STOP.\n"
        "- If you detect emergency-like content, output SAFETY.\n"
        "- Use known patient history only to personalize operational intake.\n\n"
        "- Do NOT re-ask known chart facts that already exist in Known patient context (allergies, medications, chronic conditions).\n"
        "- If that chart fact is relevant, ask only for changes since last update (for example: 'Any new allergies or reactions since your last update?').\n"
        "- If chart facts are already known and unchanged, ask the next missing intake detail instead.\n\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "decision": "ASK" | "STOP" | "SAFETY",\n'
        '  "next_question": string | null,\n'
        '  "reason": string\n'
        "}\n\n"
        f"Clinic context:\n{clinic_context}\n\n"
        f"{_patient_context_block(patient_context)}\n\n"
        f"Turn: {turn_count}/{max_turns}\n\n"
        f"Transcript:\n{transcript}"
    )
    return system_prompt, user_prompt


def final_classification_prompts(
    *,
    clinic_context: str,
    transcript: str,
    patient_context: str | None = None,
    language: str = "en",
) -> tuple[str, str]:
    normalized_language = normalize_language(language)
    language_rule = LANGUAGE_INSTRUCTION.format(language_name=language_name(normalized_language))
    system_prompt = (
        f"{SYSTEM_POLICY}\n"
        f"{language_rule}\n"
        "Return JSON only. Never return markdown fences."
    )
    user_prompt = (
        "Task: Produce operational outputs only:\n"
        "- urgency_band: low | medium | high (operational urgency, not medical diagnosis)\n"
        "- visit_category: non-diagnostic operational bucket (examples: respiratory, injury, general, skin, admin, other)\n"
        "- explanation: short operational rationale in plain language (no medical claims)\n\n"
        "Constraints:\n"
        "- Keep output grounded in pre-intake context only.\n"
        "- If transcript is mostly out-of-scope, keep explanation brief and operational without medical claims.\n\n"
        "Return JSON only with this schema:\n"
        "{\n"
        '  "urgency_band": "low" | "medium" | "high",\n'
        '  "visit_category": string,\n'
        '  "explanation": string\n'
        "}\n\n"
        f"Clinic context:\n{clinic_context}\n\n"
        f"{_patient_context_block(patient_context)}\n\n"
        f"Transcript:\n{transcript}"
    )
    return system_prompt, user_prompt

