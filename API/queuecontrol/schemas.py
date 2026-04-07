from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ModelType = Literal["rush-hour", "wait-time"]


class QueueRecordIn(BaseModel):
    record_id: int | None = None
    clinic_name: str
    patient_id: int
    arrival_time: datetime
    priority: int = Field(ge=1, le=5)
    est_duration: int = Field(ge=1)
    seen_by_doctor_time: datetime | None = None


class CollectDataRequest(BaseModel):
    days_to_simulate: int = Field(default=365, ge=1, le=3650)
    num_doctors: int = Field(default=2, ge=1, le=50)
    persist_to_db: bool = True


class PreprocessRequest(BaseModel):
    model_type: ModelType = "rush-hour"


class TrainModelRequest(BaseModel):
    model_type: ModelType


class PredictSurgeRequest(BaseModel):
    queue_records: list[QueueRecordIn] = Field(default_factory=list)
    current_time: datetime | None = None


class PredictWaitTimeRequest(BaseModel):
    clinic_name: str
    queue_records: list[QueueRecordIn] = Field(default_factory=list)
    current_time: datetime | None = None
    doctor_count: int | None = Field(default=None, ge=1, le=50)


class QueuePatientCreateRequest(BaseModel):
    clinic_name: str
    patient_id: int
    arrival_time: datetime
    priority: int = Field(ge=1, le=5)
    est_duration: int = Field(ge=1)


class QueueTriageUpdateRequest(BaseModel):
    priority: int = Field(ge=1, le=5)
    est_duration: int | None = Field(default=None, ge=1)