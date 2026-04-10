import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.loader import load_clinics_config
from app.storage.db import get_conn


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def iso_after_hours(hours: int) -> str:
    return (utc_now() + timedelta(hours=hours)).isoformat()


def iso_after_minutes(minutes: int) -> str:
    return (utc_now() + timedelta(minutes=minutes)).isoformat()


def _clinic_ids() -> list[str]:
    cfg = load_clinics_config()
    return [clinic['id'] for clinic in cfg.get('clinics', []) if clinic.get('id')]


def _demo_patient_index(patient_id: str) -> int | None:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT patient_id
            FROM patients
            WHERE role='patient' AND patient_id LIKE ?
            ORDER BY patient_id ASC
            """,
        ('demo-%',),
        ).fetchall()
        for index, row in enumerate(rows):
            if row['patient_id'] == patient_id:
                return index
        return None
    finally:
        conn.close()

PATIENT_SELECT_COLUMNS = (
    'patient_id, full_name, email, email_verified, is_admin, role, clinic_id, '
    'password_hash, medical_profile_json, professional_profile_json, created_at, updated_at, last_login_at'
)
ADMIN_ROLES = {'manager'}


def _normalized_role(role: str | None, *, fallback_is_admin: bool = False) -> str:
    cleaned = str(role or '').strip().lower()
    if cleaned in {'patient', 'staff', 'manager'}:
        return cleaned
    return 'manager' if fallback_is_admin else 'patient'


def _is_admin_role(role: str | None) -> bool:
    return _normalized_role(role) in ADMIN_ROLES


def _parse_profile_blob(raw_value: str | None) -> dict[str, Any] | None:
    if not raw_value:
        return None
    try:
        parsed = json.loads(raw_value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _serialize_profile_blob(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    cleaned = {key: value for key, value in profile.items() if value not in (None, '', [])}
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def _parse_medical_profile(raw_value: str | None) -> dict[str, Any] | None:
    return _parse_profile_blob(raw_value)


def _serialize_medical_profile(profile: dict[str, Any] | None) -> str | None:
    return _serialize_profile_blob(profile)


def _parse_professional_profile(raw_value: str | None) -> dict[str, Any] | None:
    return _parse_profile_blob(raw_value)


def _serialize_professional_profile(profile: dict[str, Any] | None) -> str | None:
    return _serialize_profile_blob(profile)


def _format_recent_history_for_context(appointments: list[dict[str, Any]]) -> str:
    if not appointments:
        return 'No prior appointment history on file.'
    lines = []
    for appointment in appointments[:5]:
        scheduled_for = str(appointment.get('scheduled_for') or '').strip()
        description = str(appointment.get('description') or 'No description recorded').strip()
        status = str(appointment.get('status') or 'unknown').strip()
        clinic_id = str(appointment.get('clinic_id') or 'unknown').strip()
        lines.append(f'- {scheduled_for} | {clinic_id} | {status} | {description}')
    return '\n'.join(lines)


def _default_booking_token(appointment_id: str) -> str:
    cleaned_id = str(appointment_id or '').strip().upper()
    if not cleaned_id:
        cleaned_id = secrets.token_hex(10).upper()
    return f'BKG-{cleaned_id}'


class SessionRepo:
    def create_session(self, clinic_id: str, patient_id: str | None = None) -> str:
        session_id = secrets.token_hex(16)
        conn = get_conn()
        try:
            conn.execute(
                'INSERT INTO sessions(session_id, clinic_id, patient_id, created_at, done) VALUES(?,?,?,?,0)',
                (session_id, clinic_id, patient_id, utc_now_iso()),
            )
            conn.commit()
            return session_id
        finally:
            conn.close()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                'SELECT session_id, clinic_id, patient_id, created_at, done FROM sessions WHERE session_id=?',
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def attach_patient(self, session_id: str, patient_id: str) -> None:
        conn = get_conn()
        try:
            conn.execute('UPDATE sessions SET patient_id=? WHERE session_id=?', (patient_id, session_id))
            conn.commit()
        finally:
            conn.close()

    def mark_done(self, session_id: str) -> None:
        conn = get_conn()
        try:
            conn.execute('UPDATE sessions SET done=1 WHERE session_id=?', (session_id,))
            conn.commit()
        finally:
            conn.close()

    def append_message(self, session_id: str, role: str, content: str) -> None:
        conn = get_conn()
        try:
            conn.execute(
                'INSERT INTO messages(session_id, role, content, ts) VALUES(?,?,?,?)',
                (session_id, role, content, utc_now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute(
                'SELECT role, content, ts FROM messages WHERE session_id=? ORDER BY id ASC',
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def store_outputs(self, session_id: str, outputs: dict[str, Any]) -> None:
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO outputs(
                  session_id, run_id, urgency_band, visit_category,
                  wait_p50_minutes, wait_p90_minutes, explanation,
                  disclaimers_json, config_snapshot_hash, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    outputs['run_id'],
                    outputs['urgency_band'],
                    outputs['visit_category'],
                    int(outputs['wait_p50_minutes']),
                    int(outputs['wait_p90_minutes']),
                    outputs['explanation'],
                    json.dumps(outputs['disclaimers']),
                    outputs['config_snapshot_hash'],
                    utc_now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


class PatientRepo:
    def get_patient_by_email(self, email: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                f'SELECT {PATIENT_SELECT_COLUMNS} FROM patients WHERE email=?',
                (email.lower(),),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_patient_by_id(self, patient_id: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                f'SELECT {PATIENT_SELECT_COLUMNS} FROM patients WHERE patient_id=?',
                (patient_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_or_update_patient(
        self,
        email: str,
        full_name: str | None = None,
        *,
        patient_id: str | None = None,
        is_admin: bool = False,
        email_verified: bool = False,
        role: str | None = None,
        clinic_id: str | None = None,
        password_hash: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = email.lower()
        existing = self.get_patient_by_email(normalized_email)
        conn = get_conn()
        now = utc_now_iso()
        try:
            if existing:
                resolved_name = (full_name or existing['full_name'] or normalized_email.split('@')[0]).strip()
                if role is None:
                    resolved_role = _normalized_role(existing.get('role'), fallback_is_admin=bool(existing.get('is_admin')))
                    resolved_is_admin = 1 if (bool(existing.get('is_admin')) or is_admin or _is_admin_role(resolved_role)) else 0
                else:
                    resolved_role = _normalized_role(role, fallback_is_admin=is_admin)
                    resolved_is_admin = 1 if (is_admin or _is_admin_role(resolved_role)) else 0
                resolved_clinic_id = clinic_id if clinic_id is not None else existing.get('clinic_id')
                if resolved_role != 'staff':
                    resolved_clinic_id = None
                resolved_password_hash = password_hash if password_hash is not None else existing.get('password_hash')
                resolved_medical_profile = existing.get('medical_profile_json')
                resolved_professional_profile = existing.get('professional_profile_json')
                conn.execute(
                    '''
                    UPDATE patients
                    SET full_name=?, email_verified=?, is_admin=?, role=?, clinic_id=?, password_hash=?, medical_profile_json=?, professional_profile_json=?, updated_at=?
                    WHERE patient_id=?
                    ''',
                    (
                        resolved_name,
                        1 if (email_verified or bool(existing['email_verified'])) else 0,
                        resolved_is_admin,
                        resolved_role,
                        resolved_clinic_id,
                        resolved_password_hash,
                        resolved_medical_profile,
                        resolved_professional_profile,
                        now,
                        existing['patient_id'],
                    ),
                )
                conn.commit()
                return self.get_patient_by_id(existing['patient_id']) or existing

            resolved_name = (full_name or normalized_email.split('@')[0]).strip()
            resolved_role = _normalized_role(role, fallback_is_admin=is_admin)
            resolved_clinic_id = clinic_id if resolved_role == 'staff' else None
            new_patient_id = patient_id or secrets.token_hex(12)
            conn.execute(
                '''
                INSERT INTO patients(
                    patient_id, full_name, email, email_verified, is_admin, role, clinic_id, password_hash, medical_profile_json, professional_profile_json, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                ''',
                (
                    new_patient_id,
                    resolved_name,
                    normalized_email,
                    1 if email_verified else 0,
                    1 if (is_admin or _is_admin_role(resolved_role)) else 0,
                    resolved_role,
                    resolved_clinic_id,
                    password_hash,
                    None,
                    None,
                    now,
                    now,
                ),
            )
            conn.commit()
            created = self.get_patient_by_id(new_patient_id)
            assert created is not None
            return created
        finally:
            conn.close()

    def register_user(
        self,
        *,
        email: str,
        full_name: str | None,
        password_hash: str,
        role: str,
        clinic_id: str | None,
    ) -> dict[str, Any]:
        existing = self.get_patient_by_email(email)
        if existing and existing.get('password_hash'):
            raise ValueError('An account with this email already exists')
        return self.create_or_update_patient(
            email,
            full_name,
            email_verified=True,
            is_admin=_is_admin_role(role),
            role=role,
            clinic_id=clinic_id,
            password_hash=password_hash,
        )

    def mark_email_verified(self, patient_id: str) -> None:
        conn = get_conn()
        now = utc_now_iso()
        try:
            conn.execute(
                'UPDATE patients SET email_verified=1, updated_at=?, last_login_at=? WHERE patient_id=?',
                (now, now, patient_id),
            )
            conn.commit()
        finally:
            conn.close()

    def create_otp(self, patient_id: str, email: str, code_hash: str, expires_at: str) -> None:
        conn = get_conn()
        try:
            conn.execute('UPDATE auth_otps SET used_at=? WHERE email=? AND used_at IS NULL', (utc_now_iso(), email.lower()))
            conn.execute(
                'INSERT INTO auth_otps(patient_id, email, code_hash, expires_at, created_at) VALUES(?,?,?,?,?)',
                (patient_id, email.lower(), code_hash, expires_at, utc_now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def consume_valid_otp(self, email: str, code_hash: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT id, patient_id FROM auth_otps
                WHERE email=? AND code_hash=? AND used_at IS NULL AND expires_at >= ?
                ORDER BY id DESC LIMIT 1
                """,
                (email.lower(), code_hash, utc_now_iso()),
            ).fetchone()
            if not row:
                return None
            conn.execute('UPDATE auth_otps SET used_at=? WHERE id=?', (utc_now_iso(), row['id']))
            conn.commit()
            return self.get_patient_by_id(row['patient_id'])
        finally:
            conn.close()

    def create_auth_session(self, patient_id: str, expires_at: str) -> str:
        token = secrets.token_urlsafe(32)
        conn = get_conn()
        now = utc_now_iso()
        try:
            conn.execute(
                'INSERT INTO auth_sessions(token, patient_id, created_at, expires_at) VALUES(?,?,?,?)',
                (token, patient_id, now, expires_at),
            )
            conn.execute(
                'UPDATE patients SET last_login_at=?, updated_at=? WHERE patient_id=?',
                (now, now, patient_id),
            )
            conn.commit()
            return token
        finally:
            conn.close()

    def get_patient_by_auth_token(self, token: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                '''
                SELECT p.patient_id, p.full_name, p.email, p.email_verified, p.is_admin, p.role, p.clinic_id,
                       p.password_hash, p.medical_profile_json, p.professional_profile_json, p.created_at, p.updated_at, p.last_login_at
                FROM auth_sessions s
                JOIN patients p ON p.patient_id = s.patient_id
                WHERE s.token=? AND s.expires_at >= ?
                LIMIT 1
                ''',
                (token, utc_now_iso()),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_auth_session(self, token: str) -> None:
        conn = get_conn()
        try:
            conn.execute('DELETE FROM auth_sessions WHERE token=?', (token,))
            conn.commit()
        finally:
            conn.close()

    def get_medical_profile(self, patient_id: str) -> dict[str, Any] | None:
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None
        return _parse_medical_profile(patient.get('medical_profile_json'))

    def get_professional_profile(self, patient_id: str) -> dict[str, Any] | None:
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None
        return _parse_professional_profile(patient.get('professional_profile_json'))

    def update_profile(
        self,
        patient_id: str,
        *,
        full_name: str | None = None,
        medical_profile: dict[str, Any] | None = None,
        professional_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return None

        conn = get_conn()
        now = utc_now_iso()
        try:
            conn.execute(
                'UPDATE patients SET full_name=?, medical_profile_json=?, professional_profile_json=?, updated_at=? WHERE patient_id=?',
                (
                    full_name if full_name is not None else patient.get('full_name'),
                    _serialize_medical_profile(medical_profile) if medical_profile is not None else patient.get('medical_profile_json'),
                    _serialize_professional_profile(professional_profile) if professional_profile is not None else patient.get('professional_profile_json'),
                    now,
                    patient_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_patient_by_id(patient_id)

    def update_medical_profile(self, patient_id: str, profile: dict[str, Any]) -> dict[str, Any] | None:
        return self.update_profile(patient_id, medical_profile=profile)

    def update_professional_profile(self, patient_id: str, profile: dict[str, Any]) -> dict[str, Any] | None:
        return self.update_profile(patient_id, professional_profile=profile)

    def build_patient_chat_context(self, patient_id: str) -> str:
        patient = self.get_patient_by_id(patient_id)
        if not patient:
            return 'No patient profile is available.'

        profile = _parse_medical_profile(patient.get('medical_profile_json')) or {}
        profile_lines = []
        ordered_fields = [
            ('date_of_birth', 'Date of birth'),
            ('sex', 'Sex'),
            ('height_cm', 'Height (cm)'),
            ('weight_kg', 'Weight (kg)'),
            ('blood_group', 'Blood group'),
            ('allergies', 'Allergies'),
            ('medications', 'Current medications'),
            ('chronic_conditions', 'Chronic conditions'),
            ('past_surgeries', 'Past surgeries'),
            ('primary_physician', 'Primary physician'),
            ('smoking_status', 'Smoking status'),
            ('pregnancy_status', 'Pregnancy status'),
            ('mobility_notes', 'Mobility notes'),
            ('medical_notes', 'Medical notes'),
        ]
        for key, label in ordered_fields:
            value = profile.get(key)
            if value not in (None, '', []):
                profile_lines.append(f'- {label}: {value}')

        appointment_history = AppointmentRepo().list_appointments_for_patient(patient_id)
        past_history = [appointment for appointment in appointment_history if str(appointment.get('status') or '').lower() != 'scheduled']

        patient_name = patient.get('full_name') or patient.get('email') or patient_id
        sections = [f'Patient on file: {patient_name}']
        sections.append('Stored profile details:' if profile_lines else 'Stored profile details: none provided.')
        if profile_lines:
            sections.extend(profile_lines)
        sections.append('Recent appointment history:')
        sections.append(_format_recent_history_for_context(past_history))
        return '\n'.join(sections)

    def list_staff_members(self, query: str | None = None, clinic_id: str | None = None) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            clauses = ["role='staff'"]
            params: list[Any] = []

            cleaned_query = str(query or '').strip().lower()
            if cleaned_query:
                clauses.append('(LOWER(COALESCE(full_name, "")) LIKE ? OR LOWER(COALESCE(email, "")) LIKE ?)')
                search_value = f"%{cleaned_query}%"
                params.extend([search_value, search_value])

            cleaned_clinic_id = str(clinic_id or '').strip()
            if cleaned_clinic_id:
                clauses.append('clinic_id=?')
                params.append(cleaned_clinic_id)

            where_sql = ' AND '.join(clauses)
            rows = conn.execute(
                f'''
                SELECT patient_id, full_name, email, role, clinic_id, email_verified, created_at, updated_at, last_login_at
                FROM patients
                WHERE {where_sql}
                ORDER BY COALESCE(clinic_id, ''), LOWER(full_name), LOWER(email)
                ''',
                params,
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_demo_user_by_email(self, email: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT patient_id, full_name, email, is_admin, role, clinic_id
                FROM patients
                WHERE patient_id LIKE ? AND LOWER(email)=?
                LIMIT 1
                """,
                ('demo-%', email.lower()),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_demo_users(self) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT patient_id, full_name, email, is_admin, role, clinic_id
                FROM patients
                WHERE patient_id LIKE ?
                ORDER BY
                    CASE role
                        WHEN 'manager' THEN 0
                        WHEN 'staff' THEN 1
                        ELSE 2
                    END,
                    LOWER(full_name),
                    LOWER(email)
                """,
            ('demo-%',),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

class AppointmentRepo:
    def create_appointment(
        self,
        patient_id: str,
        clinic_id: str,
        scheduled_for: str,
        session_id: str | None = None,
        status: str = 'scheduled',
        appointment_id: str | None = None,
        description: str | None = None,
        booking_token: str | None = None,
    ) -> dict[str, Any]:
        resolved_appointment_id = appointment_id or secrets.token_hex(12)
        resolved_booking_token = _default_booking_token(resolved_appointment_id)
        if isinstance(booking_token, str) and booking_token.strip():
            resolved_booking_token = booking_token.strip().upper()

        conn = get_conn()
        now = utc_now_iso()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO appointments(
                    appointment_id, booking_token, patient_id, clinic_id, session_id, scheduled_for, status, description, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (resolved_appointment_id, resolved_booking_token, patient_id, clinic_id, session_id, scheduled_for, status, description, now, now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT appointment_id, booking_token, patient_id, clinic_id, session_id, scheduled_for, status, COALESCE(NULLIF(TRIM(description), ''), 'General consultation') AS description, created_at, updated_at FROM appointments WHERE appointment_id=?",
                (resolved_appointment_id,),
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def list_appointments_for_patient(self, patient_id: str) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT appointment_id, booking_token, patient_id, clinic_id, session_id, scheduled_for, status, COALESCE(NULLIF(TRIM(description), ''), 'General consultation') AS description, created_at, updated_at
                FROM appointments
                WHERE patient_id=?
                ORDER BY scheduled_for DESC
                """,
                (patient_id,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def ensure_demo_appointments(
        self,
        patient_id: str,
        base_clinic_id: str | None = None,
        replace_existing: bool = False,
        include_upcoming: bool = False,
    ) -> None:
        demo_index = _demo_patient_index(patient_id)
        clinic_ids = _clinic_ids()
        if demo_index is None or not clinic_ids:
            return

        conn = get_conn()
        try:
            existing_row = conn.execute(
                'SELECT COUNT(*) AS total FROM appointments WHERE patient_id=?',
                (patient_id,),
            ).fetchone()
            existing_total = int(existing_row['total']) if existing_row else 0
            if existing_total and not replace_existing:
                return
            if replace_existing:
                conn.execute('DELETE FROM appointments WHERE patient_id=?', (patient_id,))
                conn.commit()
        finally:
            conn.close()

        now = utc_now()
        resolved_base_clinic_id = str(base_clinic_id or '').strip()
        if resolved_base_clinic_id and resolved_base_clinic_id in clinic_ids:
            base_clinic_index = clinic_ids.index(resolved_base_clinic_id)
        else:
            base_clinic_index = demo_index % len(clinic_ids)

        if include_upcoming:
            for offset in range(2):
                clinic_id = clinic_ids[(base_clinic_index + offset) % len(clinic_ids)]
                scheduled_for = (now + timedelta(days=offset + 1, hours=9 + demo_index, minutes=offset * 20)).isoformat()
                self.create_appointment(
                    patient_id=patient_id,
                    clinic_id=clinic_id,
                    scheduled_for=scheduled_for,
                    status='scheduled',
                    appointment_id=f'demo-upcoming-{patient_id}-{offset + 1}',
                    description=f'Demo upcoming visit at {clinic_id.replace("-", " ").title()}',
                )

        for offset in range(6):
            clinic_id = clinic_ids[(base_clinic_index + offset) % len(clinic_ids)]
            scheduled_for = (now - timedelta(days=offset + 2, hours=demo_index)).isoformat()
            self.create_appointment(
                patient_id=patient_id,
                clinic_id=clinic_id,
                scheduled_for=scheduled_for,
                status='completed',
                appointment_id=f'demo-history-{patient_id}-{offset + 1}',
                description=f'Demo completed visit at {clinic_id.replace("-", " ").title()}',
            )

    def remove_auto_demo_upcoming_appointments(self, patient_id: str) -> int:
        conn = get_conn()
        try:
            cursor = conn.execute(
                """
                DELETE FROM appointments
                WHERE patient_id=?
                  AND (
                    appointment_id LIKE ?
                    OR (status='scheduled' AND COALESCE(description, '') LIKE ?)
                  )
                """,
                (patient_id, 'demo-upcoming-%', 'Demo upcoming visit%'),
            )
            conn.commit()
            return int(getattr(cursor, 'rowcount', 0) or 0)
        finally:
            conn.close()

    def ensure_initial_patient_appointment(self, patient_id: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            existing = conn.execute(
                'SELECT appointment_id FROM appointments WHERE patient_id=? ORDER BY created_at DESC LIMIT 1',
                (patient_id,),
            ).fetchone()
            if existing:
                return None
        finally:
            conn.close()

        clinic_ids = _clinic_ids()
        if not clinic_ids:
            return None

        scheduled_for = (utc_now() + timedelta(days=1, hours=2)).isoformat()
        return self.create_appointment(
            patient_id=patient_id,
            clinic_id=clinic_ids[0],
            scheduled_for=scheduled_for,
            status='scheduled',
            description='Auto-booked initial consultation',
        )
    def search_appointments(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            filters = filters or {}
            params: list[Any] = []
            clauses: list[str] = []

            clinic_id = filters.get('clinic_id')
            if clinic_id:
                clauses.append('a.clinic_id=?')
                params.append(clinic_id)

            patient_query = filters.get('patient_query')
            if patient_query:
                clauses.append(
                    '(LOWER(COALESCE(p.full_name, "")) LIKE ? OR LOWER(COALESCE(p.email, "")) LIKE ? OR LOWER(COALESCE(a.booking_token, "")) LIKE ? OR LOWER(COALESCE(a.appointment_id, "")) LIKE ?)'
                )
                search_value = f"%{str(patient_query).lower()}%"
                params.extend([search_value, search_value, search_value, search_value])

            scheduled_from = filters.get('scheduled_from')
            if scheduled_from:
                clauses.append('a.scheduled_for >= ?')
                params.append(scheduled_from)

            scheduled_to = filters.get('scheduled_to')
            if scheduled_to:
                clauses.append('a.scheduled_for <= ?')
                params.append(scheduled_to)

            time_bucket = str(filters.get('time_bucket') or 'today').lower()
            now_iso = utc_now_iso()
            if time_bucket == 'today':
                today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                today_end = utc_now().replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
                clauses.append('a.scheduled_for >= ?')
                clauses.append('a.scheduled_for <= ?')
                params.extend([today_start, today_end])
            elif time_bucket == 'upcoming':
                clauses.append('a.scheduled_for > ?')
                params.append(now_iso)
            elif time_bucket == 'past':
                clauses.append('a.scheduled_for < ?')
                params.append(now_iso)

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
            rows = conn.execute(
                f'''
                SELECT a.appointment_id, a.booking_token, a.patient_id, p.full_name, p.email, a.clinic_id, a.session_id,
                       a.scheduled_for, a.status, COALESCE(NULLIF(TRIM(a.description), ''), 'General consultation') AS description, a.created_at, a.updated_at
                FROM appointments a
                JOIN patients p ON p.patient_id = a.patient_id
                {where_sql}
                ORDER BY a.scheduled_for ASC
                ''',
                params,
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def list_due_reminders(self, window_end_iso: str) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute(
                """
                SELECT a.appointment_id, a.patient_id, a.clinic_id, a.session_id, a.scheduled_for, a.status,
                       p.full_name, p.email
                FROM appointments a
                JOIN patients p ON p.patient_id = a.patient_id
                WHERE a.status='scheduled'
                  AND a.scheduled_for <= ?
                  AND a.scheduled_for >= ?
                  AND NOT EXISTS (
                    SELECT 1 FROM notification_logs n
                    WHERE n.appointment_id = a.appointment_id
                      AND n.notification_type = 'reminder_15m'
                      AND n.status = 'sent'
                  )
                ORDER BY a.scheduled_for ASC
                """,
                (window_end_iso, utc_now_iso()),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def log_notification(
        self,
        appointment_id: str,
        notification_type: str,
        scheduled_for: str,
        status: str,
        detail: str,
    ) -> None:
        conn = get_conn()
        try:
            conn.execute(
                'INSERT INTO notification_logs(appointment_id, notification_type, scheduled_for, sent_at, status, detail) VALUES(?,?,?,?,?,?)',
                (appointment_id, notification_type, scheduled_for, utc_now_iso(), status, detail),
            )
            conn.commit()
        finally:
            conn.close()


class AdminRepo:
    def list_results(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            filters = filters or {}
            params: list[Any] = []
            clauses: list[str] = []

            clinic_id = filters.get('clinic_id')
            if clinic_id:
                clauses.append('s.clinic_id=?')
                params.append(clinic_id)

            urgency_band = filters.get('urgency_band')
            if urgency_band:
                clauses.append('LOWER(o.urgency_band)=?')
                params.append(str(urgency_band).lower())

            visit_category = filters.get('visit_category')
            if visit_category:
                clauses.append('LOWER(o.visit_category)=?')
                params.append(str(visit_category).lower())

            patient_query = filters.get('patient_query')
            if patient_query:
                clauses.append('(LOWER(COALESCE(p.full_name, "")) LIKE ? OR LOWER(COALESCE(p.email, "")) LIKE ?)')
                search_value = f"%{str(patient_query).lower()}%"
                params.extend([search_value, search_value])

            created_from = filters.get('created_from')
            if created_from:
                clauses.append('o.created_at >= ?')
                params.append(created_from)

            created_to = filters.get('created_to')
            if created_to:
                clauses.append('o.created_at <= ?')
                params.append(created_to)

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
            rows = conn.execute(
                f"""
                SELECT o.session_id, s.clinic_id, s.patient_id, p.full_name, p.email,
                       o.urgency_band, o.visit_category, o.wait_p50_minutes, o.wait_p90_minutes,
                       o.explanation, o.created_at
                FROM outputs o
                JOIN sessions s ON s.session_id = o.session_id
                LEFT JOIN patients p ON p.patient_id = s.patient_id
                {where_sql}
                ORDER BY o.created_at DESC
                """,
                params,
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def _seed_demo_users_for_clinics(clinic_ids: list[str], base_users: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seed_users = [dict(user) for user in base_users]
    staff_clinics = {
        str(user.get('clinic_id') or '').strip()
        for user in seed_users
        if str(user.get('role') or '').lower() == 'staff' and str(user.get('clinic_id') or '').strip()
    }
    patient_clinics = {
        str(user.get('clinic_id') or '').strip()
        for user in seed_users
        if str(user.get('role') or '').lower() == 'patient' and str(user.get('clinic_id') or '').strip()
    }

    for clinic_id in clinic_ids:
        if clinic_id not in staff_clinics:
            slug = clinic_id.replace('-', '.')
            seed_users.append(
                {
                    'patient_id': f'demo-staff-{clinic_id}',
                    'full_name': f"Demo Staff {clinic_id.replace('-', ' ').title()}",
                    'email': f'staff.{slug}@queueiq.local',
                    'role': 'staff',
                    'clinic_id': clinic_id,
                    'is_admin': False,
                    'otp_code': '333333',
                }
            )
            staff_clinics.add(clinic_id)

        if clinic_id not in patient_clinics:
            slug = clinic_id.replace('-', '.')
            seed_users.append(
                {
                    'patient_id': f'demo-patient-{clinic_id}',
                    'full_name': f"Demo Patient {clinic_id.replace('-', ' ').title()}",
                    'email': f'patient.{slug}@queueiq.local',
                    'role': 'patient',
                    'clinic_id': clinic_id,
                    'is_admin': False,
                    'otp_code': '111111',
                }
            )
            patient_clinics.add(clinic_id)

    return seed_users


def seed_demo_data() -> dict[str, int]:
    from app.auth.demo_accounts import DEMO_USERS

    patient_repo = PatientRepo()
    appointment_repo = AppointmentRepo()
    clinic_ids = _clinic_ids()
    if not clinic_ids:
        return {
            'inserted_users': 0,
            'skipped_duplicates': 0,
            'patient_rows_seeded': 0,
        }

    seed_users = _seed_demo_users_for_clinics(clinic_ids, DEMO_USERS)
    summary = {
        'inserted_users': 0,
        'skipped_duplicates': 0,
        'patient_rows_seeded': 0,
    }

    patient_demo_index = 0
    for user in seed_users:
        user_clinic_id = user.get('clinic_id') if user.get('clinic_id') in clinic_ids else None
        existing = patient_repo.get_patient_by_email(user['email'])
        if existing:
            summary['skipped_duplicates'] += 1
            patient = existing
        else:
            patient = patient_repo.create_or_update_patient(
                user['email'],
                user['full_name'],
                patient_id=user['patient_id'],
                is_admin=bool(user['is_admin']),
                email_verified=True,
                role=user['role'],
                clinic_id=user_clinic_id,
            )
            summary['inserted_users'] += 1

        if user['role'] != 'patient':
            continue

        patient_demo_index += 1
        summary['patient_rows_seeded'] += 1
        appointment_repo.ensure_demo_appointments(
            patient['patient_id'],
            base_clinic_id=user_clinic_id,
            replace_existing=False,
            include_upcoming=False,
        )

        conn = get_conn()
        try:
            session_id = f"demo-session-{patient['patient_id']}"
            clinic_id = user_clinic_id or clinic_ids[(patient_demo_index - 1) % len(clinic_ids)]
            urgency = ['low', 'medium', 'high'][(patient_demo_index - 1) % 3]
            category = ['general', 'respiratory', 'urgent'][(patient_demo_index - 1) % 3]

            conn.execute(
                """
                INSERT INTO sessions(session_id, clinic_id, patient_id, created_at, done)
                VALUES(?,?,?,?,1)
                ON CONFLICT (session_id) DO NOTHING
                """,
                (session_id, clinic_id, patient['patient_id'], utc_now_iso()),
            )
            conn.execute(
                """
                INSERT INTO outputs(
                    session_id, run_id, urgency_band, visit_category,
                    wait_p50_minutes, wait_p90_minutes, explanation,
                    disclaimers_json, config_snapshot_hash, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT (session_id) DO NOTHING
                """,
                (
                    session_id,
                    f"demo-run-{patient['patient_id']}",
                    urgency,
                    category,
                    18 + ((patient_demo_index - 1) * 7),
                    32 + ((patient_demo_index - 1) * 11),
                    f"Demo intake summary for {patient['full_name']} at {clinic_id}.",
                    json.dumps([
                        'This is not a diagnosis.',
                        'Wait-time estimates are not guaranteed.',
                    ]),
                    f"demo-config-hash-{patient['patient_id']}",
                    utc_now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    return summary




