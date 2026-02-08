DEFAULT_DISCLAIMERS = [
    "This tool provides operational guidance only. It is not a medical diagnosis.",
    "If you think this is an emergency or severe, seek urgent in-person care or call local emergency services.",
    "Wait-time estimates are not guaranteed and may change.",
]

SYSTEM_POLICY = """You are ArrivalSignal for a clinic queue management system.
You MUST follow these rules:
- Provide operational outputs only. No diagnosis, no treatment, no medication advice.
- Ask short, neutral intake questions to support operational triage for queue planning.
- If user describes severe symptoms or emergency indicators, stop and provide safe escalation guidance.
- Keep it under ~10 turns total unless explicitly extended by the system.
"""


def prompt_next_question(clinic_context: str, transcript: str, turn_count: int, max_turns: int) -> str:
    return f"""
{SYSTEM_POLICY}

Task: Decide the next best intake question OR decide to stop.

Constraints:
- No diagnosis, no treatment, no medical instructions.
- Ask ONE question at a time.
- If enough info has been collected, output STOP.
- If you detect emergency-like content, output SAFETY.

Return JSON only with this schema:
{{
  "decision": "ASK" | "STOP" | "SAFETY",
  "next_question": string | null,
  "reason": string
}}

Clinic context:
{clinic_context}

Turn: {turn_count}/{max_turns}

Transcript:
{transcript}
""".strip()


def prompt_final_classification(clinic_context: str, transcript: str) -> str:
    return f"""
{SYSTEM_POLICY}

Task: Produce operational outputs only:
- urgency_band: low | medium | high (operational urgency, not medical diagnosis)
- visit_category: a non-diagnostic operational bucket (examples: respiratory, injury, general, skin, admin, other)
- explanation: a short operational rationale in plain language (no medical claims)

Return JSON only with this schema:
{{
  "urgency_band": "low" | "medium" | "high",
  "visit_category": string,
  "explanation": string
}}

Clinic context:
{clinic_context}

Transcript:
{transcript}
""".strip()


def prompt_safety_guardrail(transcript: str) -> str:
    return f"""
{SYSTEM_POLICY}

Task: Detect high-risk or emergency-like content in the transcript.
Examples include: trouble breathing, chest pain, severe bleeding, fainting, stroke-like symptoms, suicidal ideation,
severe allergic reaction, or user explicitly saying it is an emergency.

Return JSON only with this schema:
{{
  "is_high_risk": boolean,
  "safe_message": string
}}

If high risk, safe_message must be short and non-diagnostic, for example:
"If this may be severe or an emergency, seek urgent in-person care or call local emergency services."

Transcript:
{transcript}
""".strip()
