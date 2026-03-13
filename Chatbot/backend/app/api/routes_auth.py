import secrets

from fastapi import APIRouter, Request

from app.auth.demo_accounts import DEMO_USER_BY_EMAIL
from app.auth.utils import (
    error_response,
    get_authenticated_patient,
    get_json_body,
    hash_otp,
    validate_email,
    validate_optional_name,
    validate_otp_code,
)
from app.core.settings import settings
from app.models.schemas import AuthSessionOut, DemoUserOut, OtpRequestOut, PatientProfileOut
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
    )


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
        is_admin=bool(demo_user['is_admin']),
        email_verified=True,
    )
    if not demo_user['is_admin']:
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
