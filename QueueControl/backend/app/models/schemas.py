from typing import Literal

from pydantic import BaseModel, Field

ClinicId = Literal["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]


class ErrorResponse(BaseModel):
    detail: str = Field(description="Human-readable error description.", examples=["Clinic not found"])
    error_code: str = Field(description="Stable machine-readable error identifier.", examples=["NOT_FOUND"])
    field: str | None = Field(default=None, description="Request field associated with the error when applicable.", examples=["clinic_id"])


class ClinicSummaryOut(BaseModel):
    clinic_id: ClinicId = Field(description="QueueControl clinic identifier.", examples=["Downtown-Clinic"])
    total_patients: int = Field(ge=0, description="Total patients currently recorded for the clinic.")
    waiting_patients: int = Field(ge=0, description="Patients still waiting to be seen.")
    active_patients: int = Field(ge=0, description="Patients already marked as seen by a doctor.")


class QueuePatientOut(BaseModel):
    clinic_id: ClinicId = Field(description="Clinic that owns the queue record.")
    id: int = Field(description="Patient identifier used in the queue simulation.", examples=[1637])
    arrival_time: str = Field(description="Arrival timestamp as stored in QueueControl.", examples=["2026-03-13 09:15:00"])
    priority: int = Field(ge=1, le=5, description="Patient priority, where 1 is most urgent and 5 is least urgent.")
    est_duration: int = Field(ge=1, description="Estimated service duration in seconds.")
    seen_doctor: bool = Field(description="Whether the patient has already been picked up by a doctor.")
    actual_wait_minutes: float | None = Field(default=None, ge=0, description="Observed wait time in seconds when available.")


class ClinicQueueSummaryOut(BaseModel):
    clinic_id: ClinicId = Field(description="QueueControl clinic identifier.")
    waiting_patients: int = Field(ge=0, description="Current number of waiting patients.")
    total_patients: int = Field(ge=0, description="Current number of total patient records for the clinic.")
    next_patient_id: int | None = Field(default=None, description="Next patient expected to be served.")
    next_patient_priority: int | None = Field(default=None, ge=1, le=5, description="priority of the next patient in queue.")


class ClinicQueueDetailOut(BaseModel):
    clinic_id: ClinicId = Field(description="QueueControl clinic identifier.")
    total_patients: int = Field(ge=0, description="Total patient records currently stored for the clinic.")
    waiting_patients: int = Field(ge=0, description="Patients still waiting in the clinic queue.")
    next_patient_id: int | None = Field(default=None, description="Identifier of the next waiting patient.")
    patients: list[QueuePatientOut] = Field(description="Ordered waiting patients for the selected clinic.")


class QueueOverviewOut(BaseModel):
    clinic_count: int = Field(ge=0, description="Number of clinics managed by QueueControl.")
    total_patients: int = Field(ge=0, description="Total patient records across all clinics.")
    total_waiting_patients: int = Field(ge=0, description="Total waiting patients across all clinics.")
    clinics: list[ClinicQueueSummaryOut] = Field(description="Per-clinic queue summary collection.")


class PatientCreateIn(BaseModel):
    priority: int = Field(default=3, ge=1, le=5, description="priority to assign to the new patient.", examples=[3])


class PatientCreateOut(BaseModel):
    clinic_id: ClinicId = Field(description="Clinic where the patient was added.")
    id: int = Field(description="Generated patient identifier.")
    arrival_time: str = Field(description="Timestamp assigned at intake.")
    priority: int = Field(ge=1, le=5, description="priority assigned to the new patient.")
    est_duration: int = Field(ge=1, description="Estimated service duration in seconds.")
    seen_doctor: bool = Field(description="New patients start in the waiting state.")
    actual_wait_minutes: float | None = Field(default=None, description="Wait time is empty when the patient is first created.")
