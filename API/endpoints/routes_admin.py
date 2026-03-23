from datetime import datetime, time, timezone

from fastapi import APIRouter, Request

from Chatbot.backend.app.auth.utils import error_response, get_authenticated_patient
from Chatbot.backend.app.config.loader import get_clinic_by_id
from Chatbot.backend.app.models.schemas import AdminResultOut, AdminResultsOut
from Chatbot.backend.app.storage.repo import AdminRepo

router = APIRouter(prefix='/admin', tags=['admin'])
_ALLOWED_URGENCY = {'low', 'medium', 'high'}


def _clean_optional(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_created(value: str | None, *, end_of_day: bool):
    cleaned = _clean_optional(value)
    if not cleaned:
        return None
    try:
        if len(cleaned) == 10:
            parsed_date = datetime.fromisoformat(cleaned).date()
            parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min, tzinfo=timezone.utc)
        else:
            parsed = datetime.fromisoformat(cleaned.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
    except ValueError:
        return error_response(422, 'created date filter must be a valid ISO date or datetime', 'INVALID_FORMAT', 'created_to' if end_of_day else 'created_from')
    return parsed.isoformat()


@router.get('/results', response_model=AdminResultsOut)
async def admin_results(
    request: Request,
    clinic_id: str | None = None,
    urgency_band: str | None = None,
    visit_category: str | None = None,
    patient_query: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    if not bool(patient.get('is_admin')):
        return error_response(403, 'Admin access is required', 'FORBIDDEN')

    resolved_clinic_id = _clean_optional(clinic_id)
    if resolved_clinic_id and not get_clinic_by_id(resolved_clinic_id):
        return error_response(404, 'Clinic not found', 'NOT_FOUND', 'clinic_id')

    resolved_urgency = _clean_optional(urgency_band)
    if resolved_urgency:
        resolved_urgency = resolved_urgency.lower()
        if resolved_urgency not in _ALLOWED_URGENCY:
            return error_response(422, 'urgency_band must be one of low, medium, or high', 'INVALID_FORMAT', 'urgency_band')

    resolved_category = _clean_optional(visit_category)
    if resolved_category:
        resolved_category = resolved_category.lower()
        if len(resolved_category) > 64:
            return error_response(422, 'visit_category is too long', 'INVALID_FORMAT', 'visit_category')

    resolved_patient_query = _clean_optional(patient_query)
    if resolved_patient_query and len(resolved_patient_query) > 120:
        return error_response(422, 'patient_query is too long', 'INVALID_FORMAT', 'patient_query')

    resolved_created_from = _parse_created(created_from, end_of_day=False)
    if hasattr(resolved_created_from, 'status_code'):
        return resolved_created_from
    resolved_created_to = _parse_created(created_to, end_of_day=True)
    if hasattr(resolved_created_to, 'status_code'):
        return resolved_created_to
    if resolved_created_from and resolved_created_to and resolved_created_from > resolved_created_to:
        return error_response(422, 'created_from must be earlier than created_to', 'INVALID_RANGE', 'created_from')

    filters = {
        'clinic_id': resolved_clinic_id,
        'urgency_band': resolved_urgency,
        'visit_category': resolved_category,
        'patient_query': resolved_patient_query,
        'created_from': resolved_created_from,
        'created_to': resolved_created_to,
    }
    results = [AdminResultOut(**row) for row in AdminRepo().list_results(filters)]
    return AdminResultsOut(
        clinic_id=resolved_clinic_id,
        urgency_band=resolved_urgency,
        visit_category=resolved_category,
        patient_query=resolved_patient_query,
        created_from=resolved_created_from,
        created_to=resolved_created_to,
        total_results=len(results),
        results=results,
    )
