import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from Chatbot.backend.app.core.settings import settings

logger = logging.getLogger("queueiq.rag")

_PROMPT_LOG_DIR = Path(__file__).resolve().parents[2] / "Chatbot" / "backend" / "logs" / "prompts"
_SEPARATOR = "=" * 50


def _sanitize_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (session_id or "").strip())
    return cleaned[:120] if cleaned else "unknown_session"


def _session_log_file(session_id: str) -> Path:
    safe_session = _sanitize_session_id(session_id)
    return _PROMPT_LOG_DIR / f"prompt_session_{safe_session}.log"


def log_constructed_prompt(
    *,
    session_id: str,
    user_query: str,
    constructed_prompt: str,
    clinic_id: str | None = None,
    patient_id: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
    endpoint: str | None = None,
    retrieval_mode: str | None = None,
) -> None:
    if not getattr(settings, "enable_prompt_logging", False):
        return

    try:
        _PROMPT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        payload = (
            f"{_SEPARATOR}\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n"
            f"Session ID: {session_id}\n"
            f"Clinic ID: {clinic_id or 'n/a'}\n"
            f"Patient ID: {patient_id or 'n/a'}\n"
            f"Model: {model_name or 'n/a'}\n"
            f"Provider: {provider or 'n/a'}\n"
            f"Endpoint: {endpoint or 'n/a'}\n"
            f"Retrieval Mode: {retrieval_mode or 'n/a'}\n"
            "User Query:\n"
            f"{user_query}\n\n"
            "Constructed Prompt:\n"
            f"{constructed_prompt}\n"
            f"{_SEPARATOR}\n\n"
        )
        with _session_log_file(session_id).open("a", encoding="utf-8", errors="strict", newline="") as handle:
            handle.write(payload)
    except Exception as exc:
        logger.warning("Prompt logging failed for session_id=%s: %s", session_id, exc)
