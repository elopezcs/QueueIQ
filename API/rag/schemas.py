from typing import Any, Literal

from pydantic import BaseModel, Field, constr


RouteTarget = Literal["patient", "clinic", "mixed"]


class RagHealthOut(BaseModel):
    status: str
    database_ready: bool
    pgvector_enabled: bool


class RagModelOut(BaseModel):
    key: str
    provider: str
    model_name: str
    prompt_variant: str
    active: bool


class RagSeedOut(BaseModel):
    ok: bool
    patients_seeded: int
    clinics_seeded: int
    notes: list[str]


class RagChatStartIn(BaseModel):
    clinic_id: constr(min_length=1, max_length=64)  # type: ignore


class RagChatStartOut(BaseModel):
    session_id: str
    assistant_message: str
    disclaimers: list[str]


class RagChatTurnIn(BaseModel):
    session_id: constr(min_length=1, max_length=64)  # type: ignore
    user_message: constr(min_length=1, max_length=2000)  # type: ignore


class RagChatTurnProgress(BaseModel):
    turn_count: int
    max_turns: int


class RagChatTurnOut(BaseModel):
    assistant_message: str
    done: bool
    progress: RagChatTurnProgress


class RagChatEndIn(BaseModel):
    session_id: constr(min_length=1, max_length=64)  # type: ignore


class RagSourceItem(BaseModel):
    source_type: str
    source_id: str
    snippet: str


class RagChatEndOut(BaseModel):
    session_id: str
    urgency_band: Literal["low", "medium", "high"]
    visit_category: str
    wait_p50_minutes: int = Field(ge=0)
    wait_p90_minutes: int = Field(ge=0)
    explanation: str
    disclaimers: list[str]
    run_id: str


class RagRetrieveDebugIn(BaseModel):
    clinic_id: constr(min_length=1, max_length=64)  # type: ignore
    query: constr(min_length=1, max_length=2000)  # type: ignore


class RagRetrieveDebugOut(BaseModel):
    route: RouteTarget
    patient_context: list[dict[str, Any]]
    clinic_context: list[dict[str, Any]]

