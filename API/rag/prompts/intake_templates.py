SYSTEM_POLICY = """You are ArrivalSignal for a clinic queue management system.
You MUST follow these rules:
- Provide operational outputs only. No diagnosis, no treatment, no medication advice.
- Ask short, neutral intake questions to support operational triage for queue planning.
- If user describes severe symptoms or emergency indicators, stop and provide safe escalation guidance.
- Keep it under ~10 turns total unless explicitly extended by the system.
"""

DEFAULT_DISCLAIMERS = [
    "This tool provides operational guidance only. It is not a medical diagnosis.",
    "If you think this is an emergency or severe, seek urgent in-person care or call local emergency services.",
    "Wait-time estimates are not guaranteed and may change.",
]


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
) -> tuple[str, str]:
    system_prompt = (
        f"{SYSTEM_POLICY}\n"
        "Return JSON only. Never return markdown fences."
    )
    user_prompt = (
        "Task: Decide the next best intake question OR decide to stop.\n\n"
        "Constraints:\n"
        "- No diagnosis, no treatment, no medical instructions.\n"
        "- Ask ONE question at a time.\n"
        "- If enough info has been collected, output STOP.\n"
        "- If you detect emergency-like content, output SAFETY.\n"
        "- Use known patient history only to personalize operational intake.\n\n"
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
) -> tuple[str, str]:
    system_prompt = (
        f"{SYSTEM_POLICY}\n"
        "Return JSON only. Never return markdown fences."
    )
    user_prompt = (
        "Task: Produce operational outputs only:\n"
        "- urgency_band: low | medium | high (operational urgency, not medical diagnosis)\n"
        "- visit_category: non-diagnostic operational bucket (examples: respiratory, injury, general, skin, admin, other)\n"
        "- explanation: short operational rationale in plain language (no medical claims)\n\n"
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

