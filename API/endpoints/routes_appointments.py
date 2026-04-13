import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from Chatbot.backend.app.auth.utils import error_response, get_authenticated_patient, get_json_body
from Chatbot.backend.app.config.loader import get_clinic_by_id
from Chatbot.backend.app.models.schemas import AdminAppointmentOut, AdminAppointmentSearchOut, AppointmentListOut, AppointmentOut
from Chatbot.backend.app.services.appointment_email_helper import (
    build_appointment_confirmation_email_html,
    build_booking_preview_output_path,
    generate_confirmation_code,
    send_appointment_confirmation_email,
    write_appointment_email_preview,
)
from Chatbot.backend.app.storage.repo import AppointmentRepo, SessionRepo

router = APIRouter(tags=['appointments'])
logger = logging.getLogger('queueiq.api.appointments')
_ALLOWED_TIME_BUCKETS = {'today', 'upcoming', 'past'}
_LEGACY_CLINIC_ID_MAP = {
    'Downtown-Clinic': 'kitchener-downtown',
    'Westside-Clinic': 'waterloo-uptown',
}


def _normalize_clinic_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return _LEGACY_CLINIC_ID_MAP.get(cleaned, cleaned)


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


def _split_patient_name(full_name: object) -> tuple[str, str]:
    if not isinstance(full_name, str):
        return ('Patient', '')
    cleaned = full_name.strip()
    if not cleaned:
        return ('Patient', '')
    parts = cleaned.split()
    if len(parts) == 1:
        return (parts[0], '')
    return (parts[0], ' '.join(parts[1:]))


def _format_appointment_date_time(scheduled_for: datetime) -> tuple[str, str]:
    local_time = scheduled_for.astimezone()
    date_text = f"{local_time.strftime('%B')} {local_time.day}, {local_time.year}"
    time_text = local_time.strftime('%I:%M %p').lstrip('0')
    return date_text, time_text


def _resolve_clinic_address(clinic: dict[str, object]) -> str:
    for key in ('address', 'address_or_city', 'city', 'location'):
        value = clinic.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return 'Address available from clinic reception'


def _require_patient_account(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    if str(patient.get('role') or 'patient').lower() != 'patient':
        return None, error_response(403, 'Patient access is required', 'FORBIDDEN')
    return patient, None


def _require_dashboard_account(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, error_response(401, 'Authentication required', 'AUTH_REQUIRED')

    role = str(patient.get('role') or 'patient').lower()
    if role not in {'staff', 'manager'}:
        return None, error_response(403, 'Staff or manager access is required', 'FORBIDDEN')

    if role == 'staff':
        clinic_id = str(_normalize_clinic_id(patient.get('clinic_id')) or '').strip()
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
    clinic_id: str | None = None,
):
    dashboard_user, auth_error = _require_dashboard_account(request)
    if auth_error:
        return auth_error

    role = str(dashboard_user.get('role') or 'patient').lower()

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

    resolved_clinic_id = None
    if role == 'staff':
        resolved_clinic_id = str(_normalize_clinic_id(dashboard_user.get('clinic_id')) or '').strip()
        if isinstance(clinic_id, str) and clinic_id.strip():
            requested_clinic_id = str(_normalize_clinic_id(clinic_id) or '').strip()
            if requested_clinic_id and requested_clinic_id != resolved_clinic_id:
                return error_response(403, 'Staff can only search within their assigned clinic', 'FORBIDDEN', 'clinic_id')
    else:
        if clinic_id is not None:
            if not isinstance(clinic_id, str):
                return error_response(422, 'clinic_id must be a non-empty string', 'INVALID_FORMAT', 'clinic_id')
            cleaned_clinic_id = str(_normalize_clinic_id(clinic_id) or '').strip()
            if cleaned_clinic_id:
                if not get_clinic_by_id(cleaned_clinic_id):
                    return error_response(404, 'Clinic not found', 'NOT_FOUND', 'clinic_id')
                resolved_clinic_id = cleaned_clinic_id

    filters = {
        'clinic_id': resolved_clinic_id,
        'patient_query': resolved_patient_query,
        'scheduled_from': resolved_scheduled_from,
        'scheduled_to': resolved_scheduled_to,
        'time_bucket': resolved_time_bucket,
    }
    results = [AdminAppointmentOut(**row) for row in AppointmentRepo().search_appointments(filters)]
    return AdminAppointmentSearchOut(
        clinic_id=resolved_clinic_id,
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
    clinic = get_clinic_by_id(clinic_id)
    if not clinic:
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

    try:
        first_name, last_name = _split_patient_name(patient.get('full_name'))
        appointment_date, appointment_time = _format_appointment_date_time(scheduled_for)
        clinic_name = str(clinic.get('name') or clinic_id)
        clinic_address = _resolve_clinic_address(clinic)
        visit_type = description or 'General Consultation'
        confirmation_code = generate_confirmation_code()
        html = build_appointment_confirmation_email_html(
            patient_first_name=first_name,
            patient_last_name=last_name,
            clinic_name=clinic_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            clinic_address=clinic_address,
            visit_type=visit_type,
            confirmation_code=confirmation_code,
        )
        output_path = build_booking_preview_output_path(str(appointment.get('appointment_id') or 'unknown'))
        write_appointment_email_preview(html=html, output_path=output_path)
        send_appointment_confirmation_email(
            recipient_email=str(patient.get('email') or ''),
            patient_first_name=first_name,
            patient_last_name=last_name,
            clinic_name=clinic_name,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            clinic_address=clinic_address,
            visit_type=visit_type,
            confirmation_code=confirmation_code,
        )
    except Exception:
        logger.warning(
            'Failed to generate appointment confirmation preview or send email',
            extra={
                'appointment_id': appointment.get('appointment_id'),
                'patient_id': patient.get('patient_id'),
                'clinic_id': clinic_id,
            },
            exc_info=True,
        )

    return AppointmentOut(**appointment)
