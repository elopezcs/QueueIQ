from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.models.schemas import (
    ClinicQueueDetailOut,
    ClinicQueueSummaryOut,
    ClinicSummaryOut,
    PatientCreateOut,
    QueueOverviewOut,
    QueuePatientOut,
)

CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]
QUEUE_COLUMNS = [
    "clinic_id",
    "id",
    "arrival_time",
    "priority",
    "est_duration",
    "seen_doctor",
    "actual_wait_minutes",
]
QUEUE_CSV_PATH = Path(__file__).resolve().parents[3] / "clinic_queue.csv"


def _validate_clinic_id(clinic_id: str) -> None:
    if clinic_id not in CLINIC_IDS:
        raise ValueError("Clinic not found")


def _service_duration_for_priority(priority: int) -> int:
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]


def _load_queue_df() -> pd.DataFrame:
    if not QUEUE_CSV_PATH.exists():
        return pd.DataFrame(columns=QUEUE_COLUMNS)

    try:
        df = pd.read_csv(QUEUE_CSV_PATH)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=QUEUE_COLUMNS)

    for column in QUEUE_COLUMNS:
        if column not in df.columns:
            df[column] = None

    df = df[QUEUE_COLUMNS].copy()
    if not df.empty:
        df["id"] = pd.to_numeric(df["id"], errors="coerce").fillna(0).astype(int)
        df["priority"] = pd.to_numeric(df["priority"], errors="coerce").fillna(5).astype(int)
        df["est_duration"] = pd.to_numeric(df["est_duration"], errors="coerce").fillna(0).astype(int)
        df["actual_wait_minutes"] = pd.to_numeric(df["actual_wait_minutes"], errors="coerce")
        df["seen_doctor"] = (
            df["seen_doctor"]
            .map({"True": True, "False": False, "true": True, "false": False, True: True, False: False})
            .fillna(False)
            .astype(bool)
        )

    return df


def _save_queue_df(df: pd.DataFrame) -> None:
    QUEUE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(QUEUE_CSV_PATH, index=False)


def _clinic_df(df: pd.DataFrame, clinic_id: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=QUEUE_COLUMNS)
    return df[df["clinic_id"] == clinic_id].copy()


def _waiting_df(df: pd.DataFrame, clinic_id: str) -> pd.DataFrame:
    clinic_df = _clinic_df(df, clinic_id)
    if clinic_df.empty:
        return clinic_df
    waiting_df = clinic_df[~clinic_df["seen_doctor"]].copy()
    return waiting_df.sort_values(by=["priority", "arrival_time", "id"])


def list_clinics() -> list[ClinicSummaryOut]:
    df = _load_queue_df()
    clinics: list[ClinicSummaryOut] = []

    for clinic_id in CLINIC_IDS:
        clinic_df = _clinic_df(df, clinic_id)
        waiting_df = _waiting_df(df, clinic_id)
        clinics.append(
            ClinicSummaryOut(
                clinic_id=clinic_id,
                total_patients=len(clinic_df),
                waiting_patients=len(waiting_df),
                active_patients=len(clinic_df[clinic_df["seen_doctor"]]) if not clinic_df.empty else 0,
            )
        )

    return clinics


def list_queue_summaries() -> list[ClinicQueueSummaryOut]:
    df = _load_queue_df()
    summaries: list[ClinicQueueSummaryOut] = []

    for clinic_id in CLINIC_IDS:
        clinic_df = _clinic_df(df, clinic_id)
        waiting_df = _waiting_df(df, clinic_id)
        next_patient_id = int(waiting_df.iloc[0]["id"]) if not waiting_df.empty else None
        next_patient_priority = int(waiting_df.iloc[0]["priority"]) if not waiting_df.empty else None

        summaries.append(
            ClinicQueueSummaryOut(
                clinic_id=clinic_id,
                waiting_patients=len(waiting_df),
                total_patients=len(clinic_df),
                next_patient_id=next_patient_id,
                next_patient_priority=next_patient_priority,
            )
        )

    return summaries


def get_queue_overview() -> QueueOverviewOut:
    summaries = list_queue_summaries()
    return QueueOverviewOut(
        clinic_count=len(CLINIC_IDS),
        total_patients=sum(item.total_patients for item in summaries),
        total_waiting_patients=sum(item.waiting_patients for item in summaries),
        clinics=summaries,
    )


def get_clinic_queue_detail(clinic_id: str) -> ClinicQueueDetailOut:
    _validate_clinic_id(clinic_id)
    df = _load_queue_df()
    clinic_df = _clinic_df(df, clinic_id)
    waiting_df = _waiting_df(df, clinic_id)

    patients = [
        QueuePatientOut(
            clinic_id=row["clinic_id"],
            id=int(row["id"]),
            arrival_time=str(row["arrival_time"]),
            priority=int(row["priority"]),
            est_duration=int(row["est_duration"]),
            seen_doctor=bool(row["seen_doctor"]),
            actual_wait_minutes=float(row["actual_wait_minutes"]) if pd.notna(row["actual_wait_minutes"]) else None,
        )
        for _, row in waiting_df.iterrows()
    ]

    return ClinicQueueDetailOut(
        clinic_id=clinic_id,
        total_patients=len(clinic_df),
        waiting_patients=len(waiting_df),
        next_patient_id=int(waiting_df.iloc[0]["id"]) if not waiting_df.empty else None,
        patients=patients,
    )


def create_patient(clinic_id: str, priority: int) -> PatientCreateOut:
    _validate_clinic_id(clinic_id)
    if priority not in {1, 2, 3, 4, 5}:
        raise ValueError("priority must be between 1 and 5")

    df = _load_queue_df()
    existing_ids = set(df["id"].tolist()) if not df.empty else set()

    patient_id = random.randint(1000, 9999)
    while patient_id in existing_ids:
        patient_id = random.randint(1000, 9999)

    patient = {
        "clinic_id": clinic_id,
        "id": patient_id,
        "arrival_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "priority": priority,
        "est_duration": _service_duration_for_priority(priority),
        "seen_doctor": False,
        "actual_wait_minutes": None,
    }

    updated_df = pd.concat([df, pd.DataFrame([patient])], ignore_index=True)
    _save_queue_df(updated_df)

    return PatientCreateOut(**patient)
