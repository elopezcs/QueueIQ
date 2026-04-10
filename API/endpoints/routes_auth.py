import json
import logging
import secrets

from fastapi import APIRouter, Request

from Chatbot.backend.app.auth.utils import (
    error_response,
    get_authenticated_patient,
    get_json_body,
    hash_otp,
    hash_password,
    validate_email,
    validate_optional_name,
    validate_otp_code,
    validate_password,
    verify_password,
)
from Chatbot.backend.app.config.loader import get_clinic_by_id
from Chatbot.backend.app.core.settings import settings
from Chatbot.backend.app.models.schemas import (
    AuthSessionOut,
    DemoUserOut,
    OtpRequestOut,
    PatientMedicalProfileOut,
    PatientProfileOut,
    StaffDirectoryOut,
    StaffMemberOut,
    StaffProfessionalProfileOut,
)
from Chatbot.backend.app.services.emailer import send_otp_email
from Chatbot.backend.app.storage.repo import AppointmentRepo, PatientRepo, iso_after_hours, iso_after_minutes

router = APIRouter(prefix='/auth', tags=['auth'])
logger = logging.getLogger("queueiq.endpoints.auth")

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
    mapped = _LEGACY_CLINIC_ID_MAP.get(cleaned, cleaned)
    return mapped


def _medical_profile(patient: dict) -> PatientMedicalProfileOut | None:
    raw_value = patient.get('medical_profile_json')
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return PatientMedicalProfileOut(**parsed)


def _professional_profile(patient: dict) -> StaffProfessionalProfileOut | None:
    raw_value = patient.get('professional_profile_json')
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return StaffProfessionalProfileOut(**parsed)


def _profile(patient: dict) -> PatientProfileOut:
    return PatientProfileOut(
        patient_id=patient['patient_id'],
        full_name=patient['full_name'],
        email=patient['email'],
        email_verified=bool(patient['email_verified']),
        is_admin=bool(patient['is_admin']),
        role=str(patient.get('role') or 'patient'),
        clinic_id=_normalize_clinic_id(patient.get('clinic_id')),
        medical_profile=_medical_profile(patient),
        professional_profile=_professional_profile(patient),
    )


def _resolve_staff_clinic(value: object):
    if not isinstance(value, str) or not value.strip():
        return error_response(400, 'clinic_id is required for staff accounts', 'MISSING_FIELD', 'clinic_id')
    clinic_id = _normalize_clinic_id(value)
    if not clinic_id or not get_clinic_by_id(clinic_id):
        return error_response(404, 'Clinic not found', 'NOT_FOUND', 'clinic_id')
    return clinic_id


def _require_manager(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return None, error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    if str(patient.get('role') or 'patient').lower() != 'manager':
        return None, error_response(403, 'Manager access is required', 'FORBIDDEN')
    return patient, None


def _clean_staff_query(value: str | None):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 120:
        return error_response(422, 'query is too long', 'INVALID_FORMAT', 'query')
    return cleaned


def _optional_profile_text(value: object, field: str, *, max_length: int = 240):
    if value is None:
        return None
    if not isinstance(value, str):
        return error_response(422, f'{field} must be a string', 'INVALID_FORMAT', field)
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        return error_response(422, f'{field} is too long', 'INVALID_FORMAT', field)
    return cleaned


def _optional_profile_number(value: object, field: str, *, minimum: float = 0.0, maximum: float = 500.0):
    if value in (None, ''):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return error_response(422, f'{field} must be a number', 'INVALID_FORMAT', field)
    if number < minimum or number > maximum:
        return error_response(422, f'{field} is out of range', 'INVALID_FORMAT', field)
    return round(number, 1)


def _parse_patient_profile_payload(body: dict[str, object]):
    field_specs = {
        'date_of_birth': ('text', 32),
        'sex': ('text', 32),
        'blood_group': ('text', 16),
        'allergies': ('text', 500),
        'medications': ('text', 500),
        'chronic_conditions': ('text', 500),
        'past_surgeries': ('text', 500),
        'primary_physician': ('text', 120),
        'emergency_contact_name': ('text', 120),
        'emergency_contact_phone': ('text', 40),
        'smoking_status': ('text', 40),
        'pregnancy_status': ('text', 80),
        'mobility_notes': ('text', 300),
        'medical_notes': ('text', 800),
        'height_cm': ('number', 30.0, 260.0),
        'weight_kg': ('number', 2.0, 500.0),
    }
    parsed: dict[str, object] = {}
    for field, spec in field_specs.items():
        value = body.get(field)
        if spec[0] == 'text':
            result = _optional_profile_text(value, field, max_length=spec[1])
        else:
            result = _optional_profile_number(value, field, minimum=spec[1], maximum=spec[2])
        if hasattr(result, 'status_code'):
            return result
        parsed[field] = result
    return parsed


def _parse_staff_profile_payload(body: dict[str, object]):
    field_specs = {
        'job_title': ('text', 120),
        'department': ('text', 120),
        'license_type': ('text', 80),
        'license_number': ('text', 80),
        'license_expiry': ('text', 32),
        'specialty': ('text', 120),
        'certifications': ('text', 500),
        'years_experience': ('number', 0.0, 70.0),
        'languages_spoken': ('text', 200),
        'shift_preference': ('text', 120),
        'supervisor_name': ('text', 120),
        'employment_start_date': ('text', 32),
        'staff_notes': ('text', 800),
    }
    parsed: dict[str, object] = {}
    for field, spec in field_specs.items():
        value = body.get(field)
        if spec[0] == 'text':
            result = _optional_profile_text(value, field, max_length=spec[1])
        else:
            result = _optional_profile_number(value, field, minimum=spec[1], maximum=spec[2])
        if hasattr(result, 'status_code'):
            return result
        parsed[field] = result
    return parsed


@router.post('/register', response_model=AuthSessionOut)
async def register(request: Request):
    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    full_name = validate_optional_name(body.get('full_name'))
    if hasattr(full_name, 'status_code'):
        return full_name

    password = validate_password(body.get('password'))
    if hasattr(password, 'status_code'):
        return password

    repo = PatientRepo()
    if settings.env.lower() != 'prod' and repo.get_demo_user_by_email(email):
        return error_response(409, 'Use demo-login for local demo users', 'DEMO_LOGIN_ONLY', 'email')

    existing = repo.get_patient_by_email(email)
    if existing and existing.get('password_hash'):
        return error_response(409, 'An account with this email already exists', 'ALREADY_EXISTS', 'email')

    patient = repo.register_user(
        email=email,
        full_name=full_name if isinstance(full_name, str) else None,
        password_hash=hash_password(password),
        role='patient',
        clinic_id=None,
    )
    AppointmentRepo().ensure_initial_patient_appointment(patient['patient_id'])
    token = repo.create_auth_session(patient['patient_id'], iso_after_hours(settings.auth_session_hours))
    refreshed = repo.get_patient_by_auth_token(token)
    if not refreshed:
        return error_response(500, 'Unable to create auth session', 'INTERNAL_SERVER_ERROR')

    return AuthSessionOut(token=token, patient=_profile(refreshed))


@router.post('/staff', response_model=PatientProfileOut)
async def create_staff_account(request: Request):
    manager, auth_error = _require_manager(request)
    if auth_error:
        return auth_error

    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    full_name = validate_optional_name(body.get('full_name'))
    if hasattr(full_name, 'status_code'):
        return full_name

    password = validate_password(body.get('password'))
    if hasattr(password, 'status_code'):
        return password

    clinic_id = _resolve_staff_clinic(body.get('clinic_id'))
    if hasattr(clinic_id, 'status_code'):
        return clinic_id

    repo = PatientRepo()
    if settings.env.lower() != 'prod' and repo.get_demo_user_by_email(email):
        return error_response(409, 'Use demo-login for local demo users', 'DEMO_LOGIN_ONLY', 'email')

    existing = repo.get_patient_by_email(email)
    if existing and existing.get('password_hash'):
        return error_response(409, 'An account with this email already exists', 'ALREADY_EXISTS', 'email')

    staff_member = repo.register_user(
        email=email,
        full_name=full_name if isinstance(full_name, str) else None,
        password_hash=hash_password(password),
        role='staff',
        clinic_id=clinic_id,
    )
    return _profile(staff_member)


@router.get('/staff-members', response_model=StaffDirectoryOut)
async def list_staff_members(request: Request, query: str | None = None, clinic_id: str | None = None):
    manager, auth_error = _require_manager(request)
    if auth_error:
        return auth_error

    resolved_query = _clean_staff_query(query)
    if hasattr(resolved_query, 'status_code'):
        return resolved_query

    resolved_clinic_id = None
    if clinic_id is not None:
        if not isinstance(clinic_id, str) or not clinic_id.strip():
            return error_response(422, 'clinic_id must be a non-empty string', 'INVALID_FORMAT', 'clinic_id')
        resolved_clinic_id = clinic_id.strip()
        if not get_clinic_by_id(resolved_clinic_id):
            return error_response(404, 'Clinic not found', 'NOT_FOUND', 'clinic_id')

    results = [
        StaffMemberOut(**row)
        for row in PatientRepo().list_staff_members(query=resolved_query if isinstance(resolved_query, str) else None, clinic_id=resolved_clinic_id)
    ]
    return StaffDirectoryOut(
        clinic_id=resolved_clinic_id,
        query=resolved_query if isinstance(resolved_query, str) else None,
        total_results=len(results),
        results=results,
    )


@router.post('/login', response_model=AuthSessionOut)
async def login(request: Request):
    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    password = validate_password(body.get('password'))
    if hasattr(password, 'status_code'):
        return password

    repo = PatientRepo()
    patient = repo.get_patient_by_email(email)
    if not patient or not verify_password(password, patient.get('password_hash')):
        return error_response(401, 'Email or password is incorrect', 'INVALID_CREDENTIALS', 'email')

    if str(patient.get('role') or 'patient').lower() == 'patient':
        AppointmentRepo().ensure_initial_patient_appointment(patient['patient_id'])

    token = repo.create_auth_session(patient['patient_id'], iso_after_hours(settings.auth_session_hours))
    refreshed = repo.get_patient_by_auth_token(token)
    if not refreshed:
        return error_response(500, 'Unable to create auth session', 'INTERNAL_SERVER_ERROR')

    return AuthSessionOut(token=token, patient=_profile(refreshed))


@router.post('/demo-login', response_model=AuthSessionOut)
async def demo_login(request: Request):
    if settings.env.lower() == 'prod':
        return error_response(404, 'Not found', 'NOT_FOUND')

    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    repo = PatientRepo()
    demo_user = repo.get_demo_user_by_email(email)
    if not demo_user:
        return error_response(404, 'Demo user not found', 'NOT_FOUND', 'email')

    if demo_user['role'] == 'patient':
        AppointmentRepo().remove_auto_demo_upcoming_appointments(demo_user['patient_id'])
    repo.mark_email_verified(demo_user['patient_id'])
    token = repo.create_auth_session(demo_user['patient_id'], iso_after_hours(settings.auth_session_hours))
    refreshed = repo.get_patient_by_auth_token(token)
    if not refreshed:
        return error_response(500, 'Unable to create auth session', 'INTERNAL_SERVER_ERROR')

    logger.info("Demo login successful: patient_id=%s role=%s", refreshed.get('patient_id'), refreshed.get('role'))
    return AuthSessionOut(token=token, patient=_profile(refreshed))


@router.post('/request-otp', response_model=OtpRequestOut)
async def request_otp(request: Request):
    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    full_name = validate_optional_name(body.get('full_name'))
    if hasattr(full_name, 'status_code'):
        return full_name

    repo = PatientRepo()
    if settings.env.lower() != 'prod' and repo.get_demo_user_by_email(email):
        return error_response(409, 'Use demo-login for local demo users', 'DEMO_LOGIN_ONLY', 'email')

    patient = repo.create_or_update_patient(email, full_name if isinstance(full_name, str) else None)
    code = f"{secrets.randbelow(1000000):06d}"
    repo.create_otp(patient['patient_id'], email, hash_otp(email, code), iso_after_minutes(settings.otp_ttl_minutes))
    send_otp_email(email, patient['full_name'], code, settings.otp_ttl_minutes)

    dev_code = code if settings.env.lower() != 'prod' else None
    return OtpRequestOut(email=email, expires_in_minutes=settings.otp_ttl_minutes, dev_code=dev_code)


@router.post('/verify-otp', response_model=AuthSessionOut)
async def verify_otp(request: Request):
    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    email = validate_email(body.get('email'))
    if hasattr(email, 'status_code'):
        return email

    code = validate_otp_code(body.get('code'))
    if hasattr(code, 'status_code'):
        return code

    repo = PatientRepo()
    patient = repo.consume_valid_otp(email, hash_otp(email, code))
    if not patient:
        return error_response(401, 'OTP code is invalid or expired', 'INVALID_OTP', 'code')

    repo.mark_email_verified(patient['patient_id'])
    token = repo.create_auth_session(patient['patient_id'], iso_after_hours(settings.auth_session_hours))
    refreshed = repo.get_patient_by_auth_token(token)
    if not refreshed:
        return error_response(500, 'Unable to create auth session', 'INTERNAL_SERVER_ERROR')

    return AuthSessionOut(token=token, patient=_profile(refreshed))


@router.get('/me', response_model=PatientProfileOut)
async def me(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')
    return _profile(patient)


@router.patch('/me', response_model=PatientProfileOut)
async def update_me(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')

    body = await get_json_body(request)
    if body is None:
        return error_response(400, 'Request body must be a JSON object', 'INVALID_JSON')

    repo = PatientRepo()
    full_name = None
    if 'full_name' in body:
        full_name = validate_optional_name(body.get('full_name'))
        if hasattr(full_name, 'status_code'):
            return full_name

    role = str(patient.get('role') or 'patient').lower()
    medical_profile = None
    professional_profile = None

    if role == 'patient':
        medical_profile = _parse_patient_profile_payload(body)
        if hasattr(medical_profile, 'status_code'):
            return medical_profile
    elif role == 'staff':
        professional_profile = _parse_staff_profile_payload(body)
        if hasattr(professional_profile, 'status_code'):
            return professional_profile

    updated = repo.update_profile(
        patient['patient_id'],
        full_name=full_name if isinstance(full_name, str) else None,
        medical_profile=medical_profile if isinstance(medical_profile, dict) else None,
        professional_profile=professional_profile if isinstance(professional_profile, dict) else None,
    )
    if not updated:
        return error_response(404, 'Profile not found', 'NOT_FOUND')
    return _profile(updated)


@router.post('/logout')
async def logout(request: Request):
    patient = get_authenticated_patient(request)
    if not patient:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')

    auth_header = request.headers.get('Authorization', '').strip()
    token = auth_header[7:].strip() if auth_header.lower().startswith('bearer ') else ''
    if not token:
        return error_response(401, 'Authentication required', 'AUTH_REQUIRED')

    PatientRepo().delete_auth_session(token)
    logger.info("Logout successful: patient_id=%s", patient.get('patient_id'))
    return {'ok': True}


@router.get('/demo-users', response_model=list[DemoUserOut])
async def demo_users():
    if settings.env.lower() == 'prod':
        return error_response(404, 'Not found', 'NOT_FOUND')
    return [DemoUserOut(**user) for user in PatientRepo().list_demo_users()]



