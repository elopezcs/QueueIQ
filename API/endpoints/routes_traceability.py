from fastapi import APIRouter
from fastapi.responses import JSONResponse

from API.rag.schemas import PublicTraceabilitySummaryOut
from API.rag.services.rag_service import get_rag_service

router = APIRouter(tags=["traceability"])


def _error(status_code: int, detail: str, error_code: str, field: str | None = None) -> JSONResponse:
    payload: dict[str, str] = {"detail": detail, "error_code": error_code}
    if field:
        payload["field"] = field
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/traceability/{session_id}", response_model=PublicTraceabilitySummaryOut)
def get_public_traceability_summary(session_id: str):
    cleaned_session_id = str(session_id or "").strip()
    if not cleaned_session_id:
        return _error(400, "session_id is required and cannot be empty", "MISSING_FIELD", "session_id")

    summary = get_rag_service().public_intake_summary(session_id=cleaned_session_id)
    if not summary:
        return _error(404, "Session not found", "NOT_FOUND", "session_id")
    return PublicTraceabilitySummaryOut(**summary)
