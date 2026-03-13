import hashlib
import re
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.storage.repo import PatientRepo

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def error_response(status_code: int, detail: str, error_code: str, field: str | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "detail": detail,
        "error_code": error_code,
    }
    if field is not None:
        payload["field"] = field
    return JSONResponse(status_code=status_code, content=payload)


async def get_json_body(request: Request) -> dict[str, Any] | None:
    try:
        body = await request.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def validate_email(value: Any, field_name: str = 'email') -> JSONResponse | str:
    if not isinstance(value, str):
        return error_response(422, f'{field_name} must be a valid email address', 'INVALID_FORMAT', field_name)
    cleaned = value.strip().lower()
    if not cleaned:
        return error_response(400, f'{field_name} is required and cannot be empty', 'MISSING_FIELD', field_name)
    if len(cleaned) > 320 or not EMAIL_RE.match(cleaned):
        return error_response(422, f'{field_name} must be a valid email address', 'INVALID_FORMAT', field_name)
    return cleaned


def validate_optional_name(value: Any, field_name: str = 'full_name') -> JSONResponse | str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return error_response(422, f'{field_name} must be a non-empty string', 'INVALID_FORMAT', field_name)
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 120:
        return error_response(422, f'{field_name} has an incorrect format or length', 'INVALID_FORMAT', field_name)
    return cleaned


def validate_otp_code(value: Any, field_name: str = 'code') -> JSONResponse | str:
    if not isinstance(value, str):
        return error_response(422, f'{field_name} must be a 6-digit string', 'INVALID_FORMAT', field_name)
    cleaned = value.strip()
    if not re.fullmatch(r'\d{6}', cleaned):
        return error_response(422, f'{field_name} must be a 6-digit string', 'INVALID_FORMAT', field_name)
    return cleaned


def hash_otp(email: str, code: str) -> str:
    payload = f'{email.lower()}::{code}::{settings.auth_secret}'.encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def extract_bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get('Authorization', '').strip()
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header[7:].strip()
    return token or None


def get_authenticated_patient(request: Request) -> dict[str, Any] | None:
    token = extract_bearer_token(request)
    if not token:
        return None
    return PatientRepo().get_patient_by_auth_token(token)
