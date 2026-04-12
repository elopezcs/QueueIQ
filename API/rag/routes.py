from typing import Any

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse

from API.rag.schemas import (
    RagAuditRunItem,
    RagAuditSessionItem,
    RagAuditSessionOutputItem,
    RagAuditTimelineOut,
    RagAuditTurnItem,
    RagChatEndOut,
    RagChatStartOut,
    RagChatTurnOut,
    RagHealthOut,
    RagModelOut,
    RagRetrieveDebugOut,
    RagSeedOut,
    RagVoiceConfigOut,
    RagVoiceTranscribeOut,
)
from API.rag.services.rag_service import get_rag_service
from API.rag.services.transcription.errors import (
    TranscriptionFeatureDisabledError,
    TranscriptionProviderFailureError,
    TranscriptionProviderUnavailableError,
    TranscriptionValidationError,
)
from API.rag.services.transcription.service import TranscriptionService
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


def _preferred_language(body: dict[str, Any]) -> str:
    raw = body.get("preferred_language")
    if raw is None:
        return "en"
    if not isinstance(raw, str):
        return "en"
    normalized = raw.strip().lower()
    if normalized in {"en", "fr", "es"}:
        return normalized
    return "en"


@router.get("/health", response_model=RagHealthOut)
def rag_health():
    return RagHealthOut(**get_rag_service().health())


@router.get("/models", response_model=list[RagModelOut])
def rag_models():
    return [RagModelOut(**model) for model in get_rag_service().models()]


@router.get("/voice/config", response_model=RagVoiceConfigOut)
def rag_voice_config():
    return RagVoiceConfigOut(
        voice_input_enabled=bool(settings.voice_input_enabled),
        voice_output_enabled=bool(settings.voice_output_enabled),
        provider=(settings.voice_transcription_provider if settings.voice_input_enabled else None),
        max_duration_seconds=max(5, int(settings.voice_max_duration_seconds)),
    )


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
    preferred_language = _preferred_language(body)
    try:
        result = get_rag_service().start_session(
            patient_id=patient["patient_id"],
            clinic_id=clinic_id,
            patient_profile=patient,
            preferred_language=preferred_language,
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


@router.post(
    "/chat/transcribe",
    response_model=RagVoiceTranscribeOut,
    responses={
        400: {"description": "Bad Request"},
        403: {"description": "Feature Disabled"},
        415: {"description": "Unsupported Media Type"},
        502: {"description": "Provider Failure"},
        503: {"description": "Provider Unavailable"},
        500: {"description": "Internal Server Error"},
    },
)
async def rag_chat_transcribe(file: UploadFile | None = File(default=None)):
    if not settings.voice_input_enabled:
        return _error(403, "Voice input feature is disabled", "FEATURE_DISABLED")
    if file is None:
        return _error(400, "Audio file is required", "MISSING_FILE", "file")

    filename = str(file.filename or "").strip()
    if not filename:
        await file.close()
        return _error(400, "Uploaded file name is required", "MISSING_FILE", "file")

    content_type = str(file.content_type or "").strip() or None
    try:
        audio_bytes = await file.read()
    finally:
        await file.close()

    if not audio_bytes:
        return _error(400, "Audio file is empty", "EMPTY_AUDIO", "file")

    service = TranscriptionService()
    try:
        result = service.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            content_type=content_type,
        )
    except TranscriptionFeatureDisabledError:
        return _error(403, "Voice input feature is disabled", "FEATURE_DISABLED")
    except TranscriptionValidationError as exc:
        detail = str(exc) or "Invalid audio file"
        status_code = 415 if "Unsupported audio" in detail else 400
        code = "UNSUPPORTED_MEDIA_TYPE" if status_code == 415 else "INVALID_AUDIO"
        return _error(status_code, detail, code, "file")
    except TranscriptionProviderUnavailableError as exc:
        return _error(503, str(exc) or "Transcription provider unavailable", "TRANSCRIPTION_UNAVAILABLE")
    except TranscriptionProviderFailureError as exc:
        return _error(502, str(exc) or "Transcription failed", "TRANSCRIPTION_FAILED")
    except Exception:
        return _error(500, "Unexpected transcription error", "INTERNAL_SERVER_ERROR")

    return RagVoiceTranscribeOut(
        success=True,
        transcript=result.transcript,
        provider=result.provider,
        bytes_processed=len(audio_bytes),
    )


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


@router.get("/audit/sessions", response_model=list[RagAuditSessionItem])
def rag_audit_sessions(
    request: Request,
    patient_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    role = str(patient.get("role") or "").lower()
    return [
        RagAuditSessionItem(**row)
        for row in get_rag_service().list_audit_sessions(
            requester_patient_id=patient["patient_id"],
            requester_role=role,
            patient_id=patient_id,
            limit=max(1, min(limit, 200)),
            offset=max(0, offset),
        )
    ]


@router.get("/audit/session/{session_id}/turns", response_model=list[RagAuditTurnItem])
def rag_audit_turns(session_id: str, request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    role = str(patient.get("role") or "").lower()
    rows = get_rag_service().list_audit_turns(
        requester_patient_id=patient["patient_id"],
        requester_role=role,
        session_id=session_id,
    )
    return [RagAuditTurnItem(**row) for row in rows]


@router.get("/audit/runs", response_model=list[RagAuditRunItem])
def rag_audit_runs(
    request: Request,
    patient_id: str | None = None,
    session_id: str | None = None,
    model_key: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    role = str(patient.get("role") or "").lower()
    rows = get_rag_service().list_audit_runs(
        requester_patient_id=patient["patient_id"],
        requester_role=role,
        patient_id=patient_id,
        session_id=session_id,
        model_key=model_key,
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return [RagAuditRunItem(**row) for row in rows]


@router.get("/audit/session/{session_id}/timeline", response_model=RagAuditTimelineOut)
def rag_audit_timeline(session_id: str, request: Request):
    patient, auth_error = _require_auth_patient(request)
    if auth_error:
        return auth_error
    role = str(patient.get("role") or "").lower()
    data = get_rag_service().session_audit_timeline(
        requester_patient_id=patient["patient_id"],
        requester_role=role,
        session_id=session_id,
    )
    if not data:
        return _error(404, "Session not found", "NOT_FOUND")
    return RagAuditTimelineOut(
        session=data["session"],
        turns=[RagAuditTurnItem(**row) for row in data.get("turns", [])],
        llm_runs=[RagAuditRunItem(**row) for row in data.get("llm_runs", [])],
        session_output=RagAuditSessionOutputItem(**data["session_output"]) if data.get("session_output") else None,
    )

