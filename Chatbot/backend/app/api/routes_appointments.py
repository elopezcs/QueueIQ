from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.auth.utils import error_response, get_authenticated_patient, get_json_body
from app.config.loader import get_clinic_by_id
from app.models.schemas import AppointmentListOut, AppointmentOut
from app.storage.repo import AppointmentRepo, SessionRepo

router = APIRouter(tags=['appointments'])


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


@router.get('/me/appointments', response_model=AppointmentListOut)
async def my_appointments(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')

    appointments = AppointmentRepo().list_appointments_for_patient(patient['patient_id'])
    now = datetime.now(timezone.utc)
    upcoming: list[AppointmentOut] = []
    past: list[AppointmentOut] = []

    for appointment in appointments:
        try:
            scheduled_for = datetime.fromisoformat(appointment['scheduled_for'].replace('Z', '+00:00'))
        except ValueError:
            past.append(AppointmentOut(**appointment))
            continue

        bucket = upcoming if scheduled_for >= now and appointment['status'] == 'scheduled' else past
        bucket.append(AppointmentOut(**appointment))

    return AppointmentListOut(upcoming=upcoming, past=past)


@router.post('/appointments', response_model=AppointmentOut)
async def create_appointment(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')

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
    )
    return AppointmentOut(**appointment)
