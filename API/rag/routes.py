from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from API.rag.schemas import (
    RagChatEndOut,
    RagChatStartOut,
    RagChatTurnOut,
    RagHealthOut,
    RagModelOut,
    RagRetrieveDebugOut,
    RagSeedOut,
)
from API.rag.services.rag_service import get_rag_service
from Chatbot.backend.app.auth.utils import get_authenticated_patient
from Chatbot.backend.app.core.settings import settings

router = APIRouter(prefix="/rag", tags=["rag"])


def _error(status_code: int, detail: str, error_code: str, field: str | None = None) -> JSONResponse:
    payload: dict[str, Any] = {"detail": detail, "error_code": error_code}
    if field:
        payload["field"] = field
    return JSONResponse(status_code=status_code, content=payload)


async def _json_body(request: Request) -> dict[str, Any] | None:
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def _require_auth_patient(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, _error(401, "Authentication required", "AUTH_REQUIRED")
    return patient, None


def _required_text(body: dict[str, Any], field: str, max_length: int = 2000):
    value = body.get(field)
    if not isinstance(value, str):
        return _error(422, f"{field} must be a non-empty string", "INVALID_FORMAT", field)
    cleaned = value.strip()
    if not cleaned:
        return _error(400, f"{field} is required and cannot be empty", "MISSING_FIELD", field)
    if len(cleaned) > max_length:
        return _error(422, f"{field} has an incorrect format or length", "INVALID_FORMAT", field)
    return cleaned


@router.get("/health", response_model=RagHealthOut)
def rag_health():
    return RagHealthOut(**get_rag_service().health())


@router.get("/models", response_model=list[RagModelOut])
def rag_models():
    return [RagModelOut(**model) for model in get_rag_service().models()]


@router.post("/seed", response_model=RagSeedOut)
def rag_seed(request: Request):
    if str(settings.env).lower() != "dev":
        patient, auth_error = _require_auth_patient(request)
        if auth_error:
            return auth_error
        if str(patient.get("role") or "patient").lower() not in {"manager", "staff"}:
            return _error(403, "Staff or manager access is required", "FORBIDDEN")
    return RagSeedOut(**get_rag_service().seed())


@router.post("/chat/start", response_model=RagChatStartOut)
async def rag_chat_start(request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    body = await _json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")
    clinic_id = _required_text(body, "clinic_id", 64)
    if isinstance(clinic_id, JSONResponse):
        return clinic_id
    try:
        result = get_rag_service().start_session(
            patient_id=patient["patient_id"],
            clinic_id=clinic_id,
            patient_profile=patient,
        )
    except ValueError:
        return _error(404, "Clinic not found", "NOT_FOUND")
    return RagChatStartOut(**result)


@router.post("/chat/turn", response_model=RagChatTurnOut)
async def rag_chat_turn(request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    body = await _json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")
    session_id = _required_text(body, "session_id", 64)
    if isinstance(session_id, JSONResponse):
        return session_id
    user_message = _required_text(body, "user_message", 2000)
    if isinstance(user_message, JSONResponse):
        return user_message
    try:
        result = get_rag_service().turn(
            patient_id=patient["patient_id"],
            session_id=session_id,
            user_message=user_message,
        )
    except ValueError:
        return _error(404, "Session not found", "NOT_FOUND")
    except PermissionError:
        return _error(403, "Session does not belong to authenticated patient", "FORBIDDEN")
    except RuntimeError:
        return _error(409, "Session is already finalized", "SESSION_FINALIZED")
    return RagChatTurnOut(**result)


@router.post("/chat/end", response_model=RagChatEndOut)
async def rag_chat_end(request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    body = await _json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")
    session_id = _required_text(body, "session_id", 64)
    if isinstance(session_id, JSONResponse):
        return session_id
    try:
        result = get_rag_service().end(patient_id=patient["patient_id"], session_id=session_id)
    except ValueError:
        return _error(404, "Session not found", "NOT_FOUND")
    except PermissionError:
        return _error(403, "Session does not belong to authenticated patient", "FORBIDDEN")
    except RuntimeError:
        return _error(409, "Session has already been finalized", "SESSION_FINALIZED")
    return RagChatEndOut(**result)


@router.post("/retrieve/debug", response_model=RagRetrieveDebugOut)
async def rag_retrieve_debug(request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    body = await _json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")
    clinic_id = _required_text(body, "clinic_id", 64)
    if isinstance(clinic_id, JSONResponse):
        return clinic_id
    query = _required_text(body, "query", 2000)
    if isinstance(query, JSONResponse):
        return query
    route, patient_context, clinic_context = get_rag_service().orchestrator.retrieve_only(
        patient_id=patient["patient_id"],
        clinic_id=clinic_id,
        user_message=query,
    )
    return RagRetrieveDebugOut(
        route=route,
        patient_context=patient_context,
        clinic_context=clinic_context,
    )


@router.get("/session/{session_id}")
def rag_session_detail(session_id: str, request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    data = get_rag_service().session_detail(patient_id=patient["patient_id"], session_id=session_id)
    if not data:
        return _error(404, "Session not found", "NOT_FOUND")
    return data


@router.get("/trace/{trace_id}")
def rag_trace_detail(trace_id: str, request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    data = get_rag_service().trace_detail(trace_id)
    if not data:
        return _error(404, "Trace not found", "NOT_FOUND")
    if data.get("patient_id") != patient["patient_id"] and str(patient.get("role") or "").lower() != "manager":
        return _error(403, "Trace access denied", "FORBIDDEN")
    return data

