import logging
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Chatbot.backend.app.core.settings import settings

logger = logging.getLogger("queueiq.rag")

_PROMPT_LOG_DIR = Path(__file__).resolve().parents[2] / "Chatbot" / "backend" / "logs" / "prompts"
_SEPARATOR = "=" * 50
_ALLOWED_LOG_FORMATS = {"log", "csv", "both"}
_CSV_HEADERS = [
    "timestamp",
    "session_id",
    "clinic_id",
    "patient_id",
    "model",
    "provider",
    "endpoint",
    "retrieval_mode",
    "event_type",
    "user_query",
    "constructed_prompt",
    "llm_inference",
    "inference_source",
]


def _sanitize_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (session_id or "").strip())
    return cleaned[:120] if cleaned else "unknown_session"


def _session_log_file(session_id: str) -> Path:
    safe_session = _sanitize_session_id(session_id)
    return _PROMPT_LOG_DIR / f"prompt_session_{safe_session}.log"


def _session_csv_file(session_id: str) -> Path:
    safe_session = _sanitize_session_id(session_id)
    return _PROMPT_LOG_DIR / f"prompt_session_{safe_session}.csv"


def _prompt_log_format() -> str:
    configured = str(getattr(settings, "prompt_log_format", "both") or "both").strip().lower()
    if configured in _ALLOWED_LOG_FORMATS:
        return configured
    logger.warning("Invalid PROMPT_LOG_FORMAT=%s; defaulting to both", configured)
    return "both"


def _should_write_log() -> bool:
    return _prompt_log_format() in {"log", "both"}


def _should_write_csv() -> bool:
    return _prompt_log_format() in {"csv", "both"}


def _format_inference_payload(
    inference_json: dict[str, Any] | None = None,
    inference_source: str | None = None,
) -> str:
    if isinstance(inference_json, dict) and inference_json:
        return json.dumps(inference_json, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if inference_source:
        return f"n/a ({inference_source})"
    return "n/a"


def _append_csv_row(session_id: str, row: dict[str, str]) -> None:
    file_path = _session_csv_file(session_id)
    write_header = not file_path.exists() or file_path.stat().st_size == 0
    with file_path.open("a", encoding="utf-8", errors="strict", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


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
    inference_json: dict[str, Any] | None = None,
    inference_source: str | None = None,
) -> None:
    if not getattr(settings, "enable_prompt_logging", False):
        return

    try:
        _PROMPT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        inference_payload = _format_inference_payload(inference_json=inference_json, inference_source=inference_source)

        if _should_write_log():
            payload = (
                f"{_SEPARATOR}\n"
                f"Timestamp: {timestamp}\n"
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
            )
            if inference_json is not None or inference_source is not None:
                payload += "LLM Inference:\n" f"{inference_payload}\n"
            payload += f"{_SEPARATOR}\n\n"
            with _session_log_file(session_id).open("a", encoding="utf-8", errors="strict", newline="") as handle:
                handle.write(payload)

        if _should_write_csv():
            _append_csv_row(
                session_id=session_id,
                row={
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "clinic_id": clinic_id or "n/a",
                    "patient_id": patient_id or "n/a",
                    "model": model_name or "n/a",
                    "provider": provider or "n/a",
                    "endpoint": endpoint or "n/a",
                    "retrieval_mode": retrieval_mode or "n/a",
                    "event_type": "prompt",
                    "user_query": user_query,
                    "constructed_prompt": constructed_prompt,
                    "llm_inference": inference_payload if (inference_json is not None or inference_source is not None) else "",
                    "inference_source": inference_source or "",
                },
            )
    except Exception as exc:
        logger.warning("Prompt logging failed for session_id=%s: %s", session_id, exc)


def log_llm_inference(
    *,
    session_id: str,
    user_query: str,
    clinic_id: str | None = None,
    patient_id: str | None = None,
    model_name: str | None = None,
    provider: str | None = None,
    endpoint: str | None = None,
    retrieval_mode: str | None = None,
    inference_json: dict[str, Any] | None = None,
    inference_source: str | None = None,
) -> None:
    if not getattr(settings, "enable_prompt_logging", False):
        return

    try:
        _PROMPT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        inference_payload = _format_inference_payload(inference_json=inference_json, inference_source=inference_source)

        if _should_write_log():
            payload = (
                f"{_SEPARATOR}\n"
                f"Timestamp: {timestamp}\n"
                f"Session ID: {session_id}\n"
                f"Clinic ID: {clinic_id or 'n/a'}\n"
                f"Patient ID: {patient_id or 'n/a'}\n"
                f"Model: {model_name or 'n/a'}\n"
                f"Provider: {provider or 'n/a'}\n"
                f"Endpoint: {endpoint or 'n/a'}\n"
                f"Retrieval Mode: {retrieval_mode or 'n/a'}\n"
                "User Query:\n"
                f"{user_query}\n\n"
                "LLM Inference:\n"
                f"{inference_payload}\n"
                f"{_SEPARATOR}\n\n"
            )
            with _session_log_file(session_id).open("a", encoding="utf-8", errors="strict", newline="") as handle:
                handle.write(payload)

        if _should_write_csv():
            _append_csv_row(
                session_id=session_id,
                row={
                    "timestamp": timestamp,
                    "session_id": session_id,
                    "clinic_id": clinic_id or "n/a",
                    "patient_id": patient_id or "n/a",
                    "model": model_name or "n/a",
                    "provider": provider or "n/a",
                    "endpoint": endpoint or "n/a",
                    "retrieval_mode": retrieval_mode or "n/a",
                    "event_type": "inference",
                    "user_query": user_query,
                    "constructed_prompt": "",
                    "llm_inference": inference_payload,
                    "inference_source": inference_source or "",
                },
            )
    except Exception as exc:
        logger.warning("Inference logging failed for session_id=%s: %s", session_id, exc)
