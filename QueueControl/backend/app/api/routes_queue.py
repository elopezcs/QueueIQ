from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.schemas import (
    ClinicQueueDetailOut,
    ClinicQueueSummaryOut,
    ClinicSummaryOut,
    ErrorResponse,
    PatientCreateOut,
    QueueOverviewOut,
)
from app.services.queue_service import (
    CLINIC_IDS,
    create_patient,
    get_clinic_queue_detail,
    get_queue_overview,
    list_clinics,
    list_queue_summaries,
)

router = APIRouter(prefix="/queue-control", tags=["queue-control"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad Request"},
    404: {"model": ErrorResponse, "description": "Not Found"},
    422: {"model": ErrorResponse, "description": "Validation Error"},
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
}
SERVER_ERROR_RESPONSE = {
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
}
NOT_FOUND_AND_SERVER_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Clinic Not Found"},
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
}


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


def _validate_clinic_id(clinic_id: str) -> JSONResponse | str:
    cleaned = clinic_id.strip()
    if cleaned not in CLINIC_IDS:
        return _error(404, "Clinic not found", "NOT_FOUND", "clinic_id")
    return cleaned


def _validate_acuity(body: dict[str, Any]) -> JSONResponse | int:
    if "acuity" not in body:
        return 3

    value = body["acuity"]
    if isinstance(value, bool) or not isinstance(value, int):
        return _error(422, "acuity must be an integer between 1 and 5", "INVALID_FORMAT", "acuity")

    if value < 1 or value > 5:
        return _error(422, "acuity must be between 1 and 5", "INVALID_FORMAT", "acuity")

    return value


@router.get(
    "/clinics",
    response_model=list[ClinicSummaryOut],
    summary="List clinics",
    description="Returns QueueControl clinic summaries including total, waiting, and completed patient counts.",
    responses=SERVER_ERROR_RESPONSE,
)
def get_clinics() -> list[ClinicSummaryOut] | JSONResponse:
    try:
        return list_clinics()
    except Exception:
        return _error(500, "Unable to load clinic summaries", "INTERNAL_SERVER_ERROR")


@router.get(
    "/overview",
    response_model=QueueOverviewOut,
    summary="Get system overview",
    description="Returns an all-clinic QueueControl overview with system-level totals and per-clinic queue summaries.",
    responses=SERVER_ERROR_RESPONSE,
)
def get_overview() -> QueueOverviewOut | JSONResponse:
    try:
        return get_queue_overview()
    except Exception:
        return _error(500, "Unable to load queue overview", "INTERNAL_SERVER_ERROR")


@router.get(
    "/queues",
    response_model=list[ClinicQueueSummaryOut],
    summary="List queue summaries",
    description="Returns one queue summary per clinic, including the next waiting patient when available.",
    responses=SERVER_ERROR_RESPONSE,
)
def get_queues() -> list[ClinicQueueSummaryOut] | JSONResponse:
    try:
        return list_queue_summaries()
    except Exception:
        return _error(500, "Unable to load queue summaries", "INTERNAL_SERVER_ERROR")


@router.get(
    "/clinics/{clinic_id}/queue",
    response_model=ClinicQueueDetailOut,
    summary="Get clinic queue details",
    description="Returns the current waiting queue for a single clinic, ordered by acuity and arrival time.",
    responses=NOT_FOUND_AND_SERVER_ERROR_RESPONSES,
)
def get_clinic_queue(clinic_id: str) -> ClinicQueueDetailOut | JSONResponse:
    validated_clinic_id = _validate_clinic_id(clinic_id)
    if isinstance(validated_clinic_id, JSONResponse):
        return validated_clinic_id

    try:
        return get_clinic_queue_detail(validated_clinic_id)
    except ValueError:
        return _error(404, "Clinic not found", "NOT_FOUND", "clinic_id")
    except Exception:
        return _error(500, "Unable to load clinic queue", "INTERNAL_SERVER_ERROR")


@router.post(
    "/clinics/{clinic_id}/patients",
    response_model=PatientCreateOut,
    status_code=201,
    summary="Add patient to clinic queue",
    description="Creates a new waiting patient record for the selected clinic using the provided acuity value.",
    responses=ERROR_RESPONSES,
)
async def add_patient(clinic_id: str, request: Request) -> PatientCreateOut | JSONResponse:
    validated_clinic_id = _validate_clinic_id(clinic_id)
    if isinstance(validated_clinic_id, JSONResponse):
        return validated_clinic_id

    body = await _get_json_body(request)
    if body is None:
        return _error(400, "Request body must be a JSON object", "INVALID_JSON")

    acuity = _validate_acuity(body)
    if isinstance(acuity, JSONResponse):
        return acuity

    try:
        return create_patient(clinic_id=validated_clinic_id, acuity=acuity)
    except ValueError as exc:
        detail = str(exc)
        if "acuity" in detail.lower():
            return _error(422, detail, "INVALID_FORMAT", "acuity")
        return _error(404, detail, "NOT_FOUND", "clinic_id")
    except Exception:
        return _error(500, "Unable to add patient to clinic queue", "INTERNAL_SERVER_ERROR")
