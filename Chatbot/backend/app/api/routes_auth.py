import secrets

from fastapi import APIRouter, Request

from app.auth.demo_accounts import DEMO_USER_BY_EMAIL
from app.auth.utils import (
    error_response,
    get_authenticated_patient,
    get_json_body,
    hash_otp,
    hash_password,
    role_is_admin,
    validate_email,
    validate_optional_name,
    validate_otp_code,
    validate_password,
    verify_password,
)
from app.config.loader import get_clinic_by_id
from app.core.settings import settings
from app.models.schemas import (
    AuthSessionOut,
    DemoUserOut,
    OtpRequestOut,
    PatientProfileOut,
    StaffDirectoryOut,
    StaffMemberOut,
)
from app.services.emailer import send_otp_email
from app.storage.repo import AppointmentRepo, PatientRepo, iso_after_hours, iso_after_minutes

router = APIRouter(prefix='/auth', tags=['auth'])


def _profile(patient: dict) -> PatientProfileOut:
    return PatientProfileOut(
        patient_id=patient['patient_id'],
        full_name=patient['full_name'],
        email=patient['email'],
        email_verified=bool(patient['email_verified']),
        is_admin=bool(patient['is_admin']),
        role=str(patient.get('role') or 'patient'),
        clinic_id=patient.get('clinic_id'),
    )


def _resolve_staff_clinic(value: object):
    if not isinstance(value, str) or not value.strip():
        return error_response(400, 'clinic_id is required for staff accounts', 'MISSING_FIELD', 'clinic_id')
    clinic_id = value.strip()
    if not get_clinic_by_id(clinic_id):
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

    if email in DEMO_USER_BY_EMAIL and settings.env.lower() != 'prod':
        return error_response(409, 'Use demo-login for local demo users', 'DEMO_LOGIN_ONLY', 'email')

    repo = PatientRepo()
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

    demo_user = DEMO_USER_BY_EMAIL.get(email)
    if not demo_user:
        return error_response(404, 'Demo user not found', 'NOT_FOUND', 'email')

    repo = PatientRepo()
    patient = repo.create_or_update_patient(
        email,
        demo_user['full_name'],
        patient_id=demo_user['patient_id'],
        is_admin=role_is_admin(demo_user['role']),
        email_verified=True,
        role=demo_user['role'],
        clinic_id=demo_user['clinic_id'],
    )
    if demo_user['role'] == 'patient':
        AppointmentRepo().ensure_demo_appointments(patient['patient_id'])
    repo.mark_email_verified(patient['patient_id'])
    token = repo.create_auth_session(patient['patient_id'], iso_after_hours(settings.auth_session_hours))
    refreshed = repo.get_patient_by_auth_token(token)
    if not refreshed:
        return error_response(500, 'Unable to create auth session', 'INTERNAL_SERVER_ERROR')

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

    if email in DEMO_USER_BY_EMAIL and settings.env.lower() != 'prod':
        return error_response(409, 'Use demo-login for local demo users', 'DEMO_LOGIN_ONLY', 'email')

    repo = PatientRepo()
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
    return {'ok': True}


@router.get('/demo-users', response_model=list[DemoUserOut])
async def demo_users():
    if settings.env.lower() == 'prod':
        return error_response(404, 'Not found', 'NOT_FOUND')
    return [DemoUserOut(**{k: v for k, v in user.items() if k != 'otp_code'}) for user in PatientRepo().list_demo_users()]
