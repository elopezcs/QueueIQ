from typing import Literal

from pydantic import BaseModel, Field, constr


class ClinicOut(BaseModel):
    id: str
    name: str
    address_or_city: str


class ClinicStatusOut(BaseModel):
    queue_length: int
    servers_busy: int
    servers_total: int
    updated_at: str


class ChatStartIn(BaseModel):
    clinic_id: constr(min_length=1, max_length=64)  # type: ignore


class ChatStartOut(BaseModel):
    session_id: str
    assistant_message: str
    disclaimers: list[str]


class ChatTurnIn(BaseModel):
    session_id: constr(min_length=1, max_length=64)  # type: ignore
    user_message: constr(min_length=1, max_length=2000)  # type: ignore


class ChatTurnProgress(BaseModel):
    turn_count: int
    max_turns: int


class ChatTurnOut(BaseModel):
    assistant_message: str
    done: bool
    progress: ChatTurnProgress


class ChatEndIn(BaseModel):
    session_id: constr(min_length=1, max_length=64)  # type: ignore


UrgencyBand = Literal['low', 'medium', 'high']


class ChatEndOut(BaseModel):
    session_id: str
    urgency_band: UrgencyBand
    visit_category: str
    wait_p50_minutes: int = Field(ge=0)
    wait_p90_minutes: int = Field(ge=0)
    explanation: str
    disclaimers: list[str]
    run_id: str


class PatientProfileOut(BaseModel):
    patient_id: str
    full_name: str
    email: str
    email_verified: bool
    is_admin: bool


class OtpRequestOut(BaseModel):
    email: str
    expires_in_minutes: int = Field(ge=1)
    dev_code: str | None = None


class AuthSessionOut(BaseModel):
    token: str
    patient: PatientProfileOut


AppointmentStatus = Literal['scheduled', 'completed', 'cancelled']


class AppointmentOut(BaseModel):
    appointment_id: str
    patient_id: str
    clinic_id: str
    session_id: str | None = None
    scheduled_for: str
    status: AppointmentStatus
    created_at: str
    updated_at: str


class AppointmentListOut(BaseModel):
    upcoming: list[AppointmentOut]
    past: list[AppointmentOut]


class AdminResultOut(BaseModel):
    session_id: str
    clinic_id: str
    patient_id: str | None = None
    full_name: str | None = None
    email: str | None = None
    urgency_band: str
    visit_category: str
    wait_p50_minutes: int
    wait_p90_minutes: int
    explanation: str
    created_at: str


class AdminResultsOut(BaseModel):
    clinic_id: str | None = None
    urgency_band: str | None = None
    visit_category: str | None = None
    patient_query: str | None = None
    created_from: str | None = None
    created_to: str | None = None
    total_results: int
    results: list[AdminResultOut]


class DemoUserOut(BaseModel):
    patient_id: str
    full_name: str
    email: str
    is_admin: bool
