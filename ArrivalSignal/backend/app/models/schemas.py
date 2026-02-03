from pydantic import BaseModel, Field, constr
from typing import Literal


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


UrgencyBand = Literal["low", "medium", "high"]


class ChatEndOut(BaseModel):
    session_id: str
    urgency_band: UrgencyBand
    visit_category: str
    wait_p50_minutes: int = Field(ge=0)
    wait_p90_minutes: int = Field(ge=0)
    explanation: str
    disclaimers: list[str]
    run_id: str
