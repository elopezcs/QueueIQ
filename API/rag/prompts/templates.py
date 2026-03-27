from typing import Any


DEFAULT_RAG_DISCLAIMERS = [
    "This assistant is for informational support and clinic operations only.",
    "It does not provide diagnosis, treatment plans, or medication prescriptions.",
    "If symptoms are severe or sudden, contact emergency services immediately.",
]


def system_prompt_for_variant(prompt_variant: str) -> str:
    base = (
        "You are QueueIQ's clinic assistant. Use only provided context. "
        "Do not invent facts. Keep responses concise and safe. "
        "If context is insufficient, say so clearly."
    )
    if prompt_variant == "qwen":
        return base + " Reply as strict JSON with keys: assistant_message, done."
    return base + " Return only JSON with keys: assistant_message, done."


def user_prompt(
    *,
    question: str,
    route: str,
    patient_context: list[dict[str, Any]],
    clinic_context: list[dict[str, Any]],
) -> str:
    return (
        "Use this retrieved context only.\n"
        f"Route: {route}\n"
        f"Patient context: {patient_context}\n"
        f"Clinic context: {clinic_context}\n"
        f"User message: {question}\n\n"
        "Output JSON: {\"assistant_message\": str, \"done\": bool}"
    )

