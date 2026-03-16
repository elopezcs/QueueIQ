from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.auth.utils import error_response, get_authenticated_patient, get_json_body
from app.config.loader import get_clinic_by_id
from app.models.schemas import AdminAppointmentOut, AdminAppointmentSearchOut, AppointmentListOut, AppointmentOut
from app.storage.repo import AppointmentRepo, SessionRepo

router = APIRouter(tags=['appointments'])
_ALLOWED_TIME_BUCKETS = {'today', 'upcoming', 'past'}


def _parse_scheduled_for(value: object):
    if not isinstance(value, str) or not value.strip():
        return error_response(400, 'scheduled_for is required and cannot be empty', 'MISSING_FIELD', 'scheduled_for')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return error_response(422, 'scheduled_for must be a valid ISO datetime', 'INVALID_FORMAT', 'scheduled_for')
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_description(value: object):
    if value is None:
        return None
    if not isinstance(value, str):
        return error_response(422, 'description must be a string', 'INVALID_FORMAT', 'description')
    cleaned = value.strip()
    if len(cleaned) > 280:
        return error_response(422, 'description is too long', 'INVALID_FORMAT', 'description')
    return cleaned or None


def _require_patient_account(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    if str(patient.get('role') or 'patient').lower() != 'patient':
        return None, error_response(403, 'Patient access is required', 'FORBIDDEN')
    return patient, None


def _require_staff_account(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    if str(patient.get('role') or 'patient').lower() != 'staff':
        return None, error_response(403, 'Staff access is required', 'FORBIDDEN')
    clinic_id = str(patient.get('clinic_id') or '').strip()
    if not clinic_id:
        return None, error_response(403, 'Staff account is missing an assigned clinic', 'FORBIDDEN')
    return patient, None


@router.get('/me/appointments', response_model=AppointmentListOut)
async def my_appointments(request: Request):
    patient, auth_error = _require_patient_account(request)
    if auth_error:
        return auth_error

    appointments = AppointmentRepo().list_appointments_for_patient(patient['patient_id'])
    now = datetime.now(timezone.utc)
    today = now.date()
    current: list[AppointmentOut] = []
    upcoming: list[AppointmentOut] = []
    past: list[AppointmentOut] = []

    for appointment in appointments:
        try:
            scheduled_for = datetime.fromisoformat(appointment['scheduled_for'].replace('Z', '+00:00'))
        except ValueError:
            past.append(AppointmentOut(**appointment))
            continue

        serialized = AppointmentOut(**appointment)
        if scheduled_for.date() == today and appointment['status'] == 'scheduled':
            current.append(serialized)
        elif scheduled_for >= now and appointment['status'] == 'scheduled':
            upcoming.append(serialized)
        else:
            past.append(serialized)

    return AppointmentListOut(current=current, upcoming=upcoming, past=past)


@router.get('/staff/appointments', response_model=AdminAppointmentSearchOut)
async def staff_appointments(
    request: Request,
    time_bucket: str = 'today',
    patient_query: str | None = None,
    scheduled_from: str | None = None,
    scheduled_to: str | None = None,
):
    staff_member, auth_error = _require_staff_account(request)
    if auth_error:
        return auth_error

    resolved_time_bucket = str(time_bucket or 'today').strip().lower()
    if resolved_time_bucket not in _ALLOWED_TIME_BUCKETS:
        return error_response(422, 'time_bucket must be today, upcoming, or past', 'INVALID_FORMAT', 'time_bucket')

    resolved_patient_query = patient_query.strip() if isinstance(patient_query, str) and patient_query.strip() else None
    if resolved_patient_query and len(resolved_patient_query) > 120:
        return error_response(422, 'patient_query is too long', 'INVALID_FORMAT', 'patient_query')

    resolved_scheduled_from = None
    if scheduled_from:
        parsed_from = _parse_scheduled_for(scheduled_from)
        if hasattr(parsed_from, 'status_code'):
            return parsed_from
        resolved_scheduled_from = parsed_from.isoformat()

    resolved_scheduled_to = None
    if scheduled_to:
        parsed_to = _parse_scheduled_for(scheduled_to)
        if hasattr(parsed_to, 'status_code'):
            return parsed_to
        resolved_scheduled_to = parsed_to.isoformat()

    if resolved_scheduled_from and resolved_scheduled_to and resolved_scheduled_from > resolved_scheduled_to:
        return error_response(422, 'scheduled_from must be earlier than scheduled_to', 'INVALID_RANGE', 'scheduled_from')

    filters = {
        'clinic_id': staff_member['clinic_id'],
        'patient_query': resolved_patient_query,
        'scheduled_from': resolved_scheduled_from,
        'scheduled_to': resolved_scheduled_to,
        'time_bucket': resolved_time_bucket,
    }
    results = [AdminAppointmentOut(**row) for row in AppointmentRepo().search_appointments(filters)]
    return AdminAppointmentSearchOut(
        clinic_id=staff_member['clinic_id'],
        time_bucket=resolved_time_bucket,
        patient_query=resolved_patient_query,
        scheduled_from=resolved_scheduled_from,
        scheduled_to=resolved_scheduled_to,
        total_results=len(results),
        results=results,
    )


@router.post('/appointments', response_model=AppointmentOut)
async def create_appointment(request: Request):
    patient, auth_error = _require_patient_account(request)
    if auth_error:
        return auth_error

    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    clinic_id = body.get('clinic_id')
    if not isinstance(clinic_id, str) or not clinic_id.strip():
        return error_response(400, 'clinic_id is required and cannot be empty', 'MISSING_FIELD', 'clinic_id')
    clinic_id = clinic_id.strip()
    if not get_clinic_by_id(clinic_id):
        return error_response(404, 'Clinic not found', 'NOT_FOUND', 'clinic_id')

    scheduled_for = _parse_scheduled_for(body.get('scheduled_for'))
    if hasattr(scheduled_for, 'status_code'):
        return scheduled_for

    description = _parse_description(body.get('description'))
    if hasattr(description, 'status_code'):
        return description

    session_id = body.get('session_id')
    if session_id is not None:
        if not isinstance(session_id, str) or not session_id.strip():
            return error_response(422, 'session_id must be a non-empty string', 'INVALID_FORMAT', 'session_id')
        session = SessionRepo().get_session(session_id.strip())
        if not session:
            return error_response(404, 'Session not found', 'NOT_FOUND', 'session_id')
        SessionRepo().attach_patient(session_id.strip(), patient['patient_id'])
        session_id = session_id.strip()

    appointment = AppointmentRepo().create_appointment(
        patient_id=patient['patient_id'],
        clinic_id=clinic_id,
        scheduled_for=scheduled_for.isoformat(),
        session_id=session_id,
        description=description,
    )
    return AppointmentOut(**appointment)
