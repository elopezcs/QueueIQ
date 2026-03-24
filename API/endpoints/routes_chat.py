import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from Chatbot.backend.app.agent.orchestrator import ChatOrchestrator
from Chatbot.backend.app.config.loader import get_clinic_by_id
from Chatbot.backend.app.models.schemas import ChatEndOut, ChatStartOut, ChatTurnOut
from Chatbot.backend.app.storage.db import get_conn
from Chatbot.backend.app.storage.repo import SessionRepo

router = APIRouter()
logger = logging.getLogger("queueiq.endpoints.chat")


def _error(status_code: int, detail: str, error_code: str, field: str | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
    }
    if field is not None:
        payload["field"] = field
    return JSONResponse(status_code=status_code, content=payload)


async def _get_json_body(request: Request) -> dict[str, Any] | None:
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def _validate_required_string(
    body: dict[str, Any],
    field_name: str,
    *,
    max_length: int = 64,
) -> JSONResponse | str:
    if field_name not in body:
        return _error(
            400,
            f"{field_name} is required and cannot be empty",
            "MISSING_FIELD",
            field_name,
        )

    value = body[field_name]
    if not isinstance(value, str):
        return _error(
            422,
            f"{field_name} must be a non-empty string",
            "INVALID_FORMAT",
            field_name,
        )

    cleaned = value.strip()
    if cleaned == "":
        return _error(
            400,
            f"{field_name} is required and cannot be empty",
            "MISSING_FIELD",
            field_name,
        )

    if len(cleaned) > max_length:
        return _error(
            422,
            f"{field_name} has an incorrect format or length",
            "INVALID_FORMAT",
            field_name,
        )

    return cleaned


def _session_output_exists(session_id: str) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT 1 FROM outputs WHERE session_id=? LIMIT 1",
            (session_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


@router.post(
    "/chat/start",
    response_model=ChatStartOut,
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Clinic Not Found"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def chat_start(request: Request):
    body = await _get_json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")

    clinic_id = _validate_required_string(body, "clinic_id", max_length=64)
    if isinstance(clinic_id, JSONResponse):
        return clinic_id

    clinic = get_clinic_by_id(clinic_id)
    if not clinic:
        return _error(404, "Clinic not found", "NOT_FOUND")

    try:
        repo = SessionRepo()
        session_id = repo.create_session(clinic_id=clinic_id)
        logger.info("Chat session started: session_id=%s clinic_id=%s", session_id, clinic_id)

        orchestrator = ChatOrchestrator()
        assistant_message, disclaimers = orchestrator.first_message(clinic=clinic)

        repo.append_message(session_id, role="assistant", content=assistant_message)
        return ChatStartOut(
            session_id=session_id,
            assistant_message=assistant_message,
            disclaimers=disclaimers,
        )
    except Exception:
        return _error(500, "Unable to create chat session", "INTERNAL_SERVER_ERROR")


@router.post(
    "/chat/turn",
    response_model=ChatTurnOut,
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Session Not Found"},
        409: {"description": "Conflict"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def chat_turn(request: Request):
    body = await _get_json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")

    session_id = _validate_required_string(body, "session_id", max_length=64)
    if isinstance(session_id, JSONResponse):
        return session_id

    user_message = _validate_required_string(body, "user_message", max_length=2000)
    if isinstance(user_message, JSONResponse):
        return user_message

    try:
        repo = SessionRepo()
        session = repo.get_session(session_id)
        if not session:
            return _error(404, "Session not found", "NOT_FOUND")

        if bool(session.get("done")) or _session_output_exists(session_id):
            return _error(409, "Session is already finalized", "SESSION_FINALIZED")

        clinic = get_clinic_by_id(session["clinic_id"])
        if not clinic:
            return _error(500, "Clinic config missing", "INTERNAL_SERVER_ERROR")

        repo.append_message(session_id, role="user", content=user_message)

        orchestrator = ChatOrchestrator()
        assistant_message, done, progress = orchestrator.next_turn(
            clinic=clinic,
            transcript=repo.get_transcript(session_id),
        )

        repo.append_message(session_id, role="assistant", content=assistant_message)

        if done:
            repo.mark_done(session_id)

        logger.info("Chat turn processed: session_id=%s done=%s", session_id, done)
        return ChatTurnOut(
            assistant_message=assistant_message,
            done=done,
            progress=progress,
        )
    except Exception:
        return _error(500, "Unable to process chat turn", "INTERNAL_SERVER_ERROR")


@router.post(
    "/chat/end",
    response_model=ChatEndOut,
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Session Not Found"},
        409: {"description": "Conflict"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def chat_end(request: Request):
    body = await _get_json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")

    session_id = _validate_required_string(body, "session_id", max_length=64)
    if isinstance(session_id, JSONResponse):
        return session_id

    try:
        repo = SessionRepo()
        session = repo.get_session(session_id)
        if not session:
            return _error(404, "Session not found", "NOT_FOUND")

        if _session_output_exists(session_id):
            return _error(409, "Session has already been finalized", "SESSION_FINALIZED")

        clinic = get_clinic_by_id(session["clinic_id"])
        if not clinic:
            return _error(500, "Clinic config missing", "INTERNAL_SERVER_ERROR")

        transcript = repo.get_transcript(session_id)

        orchestrator = ChatOrchestrator()
        result = orchestrator.finalize(
            clinic=clinic,
            transcript=transcript,
        )
        result["session_id"] = session_id

        repo.store_outputs(
            session_id=session_id,
            outputs=result,
        )
        logger.info("Chat session finalized: session_id=%s run_id=%s", session_id, result.get("run_id"))

        return ChatEndOut(**result)
    except Exception:
        return _error(500, "Unable to finalize chat session", "INTERNAL_SERVER_ERROR")
