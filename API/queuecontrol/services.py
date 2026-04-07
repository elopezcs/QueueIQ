from __future__ import annotations

import importlib.util
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from database.database_manager import DatabaseManager

logger = logging.getLogger("queueiq.api.queuecontrol")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUEUECONTROL_ROOT = REPO_ROOT / "QueueControl"
RUSH_HOUR_SCRIPT_PATH = QUEUECONTROL_ROOT / "model-training" / "rush_hour_predictor_model.py"
WAIT_TIME_SCRIPT_PATH = QUEUECONTROL_ROOT / "model-training" / "wait_time_predictor_model.py"
SYNTHETIC_DATA_SCRIPT_PATH = QUEUECONTROL_ROOT / "synthetic-data-generation" / "clinical_annual_visits.py"
RUSH_HOUR_MODEL_PATH = QUEUECONTROL_ROOT / "models" / "rush_hour_predictor_model.joblib"
RUSH_HOUR_METRICS_PATH = QUEUECONTROL_ROOT / "models" / "rush_hour_predictor_metrics.json"
WAIT_TIME_MODEL_PATH = QUEUECONTROL_ROOT / "models" / "wait_time_predictor_model.joblib"
WAIT_TIME_METRICS_PATH = QUEUECONTROL_ROOT / "models" / "wait_time_predictor_metrics.json"

RUSH_HOUR_FEATURES = [
    "is_weekend",
    "day_sin",
    "day_cos",
    "hour_sin",
    "hour_cos",
    "queue_length_at_arrival",
    "arrivals_last_1_hour",
    "avg_wait_last_1_hour",
]
WAIT_TIME_FEATURES = [
    "clinic_id",
    "is_weekend",
    "day_sin",
    "day_cos",
    "hour_sin",
    "hour_cos",
    "queue_length_at_arrival",
    "arrivals_last_1_hour",
    "avg_wait_last_1_hour",
]


def _build_db_manager() -> DatabaseManager:
    manager = DatabaseManager()
    manager.init_db()
    return manager


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module '{module_name}' from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_model_type(model_type: str) -> str:
    normalized = model_type.strip().lower()
    if normalized not in {"rush-hour", "wait-time"}:
        raise ValueError("model_type must be either 'rush-hour' or 'wait-time'.")
    return normalized


def _to_python(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    normalized_df = df.copy()
    for column in normalized_df.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized_df[column]):
            normalized_df[column] = normalized_df[column].apply(
                lambda value: None if pd.isna(value) else pd.Timestamp(value).isoformat()
            )

    normalized_df = normalized_df.where(pd.notna(normalized_df), None)
    return [
        {key: _to_python(value) for key, value in row.items()}
        for row in normalized_df.to_dict(orient="records")
    ]


def queue_records_to_df(queue_records: list[dict[str, Any]]) -> pd.DataFrame:
    if not queue_records:
        return pd.DataFrame(
            columns=[
                "record_id",
                "clinic_name",
                "patient_id",
                "arrival_time",
                "priority",
                "est_duration",
                "seen_by_doctor_time",
            ]
        )

    df = pd.DataFrame(queue_records)
    for column in ("arrival_time", "seen_by_doctor_time"):
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")
    return df


def _load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _load_rush_hour_model():
    if not RUSH_HOUR_MODEL_PATH.exists():
        return None
    return joblib.load(RUSH_HOUR_MODEL_PATH)


def _load_wait_time_model() -> dict[str, Any] | None:
    if not WAIT_TIME_MODEL_PATH.exists():
        return None
    return joblib.load(WAIT_TIME_MODEL_PATH)


def get_clinics() -> list[dict[str, Any]]:
    return dataframe_to_records(_build_db_manager().fetch_clinics())


def get_waiting_queue() -> list[dict[str, Any]]:
    return dataframe_to_records(_build_db_manager().fetch_queue())


def get_queue_activity() -> list[dict[str, Any]]:
    return dataframe_to_records(_build_db_manager().fetch_queue_activity())


def add_queue_patient(
    clinic_name: str,
    patient_id: int,
    arrival_time: datetime,
    priority: int,
    est_duration: int,
) -> dict[str, Any]:
    db_manager = _build_db_manager()
    db_manager.insert_patient(clinic_name, patient_id, arrival_time, priority, est_duration)
    return {
        "clinic_name": clinic_name,
        "patient_id": patient_id,
        "arrival_time": arrival_time.isoformat(),
        "priority": priority,
        "est_duration": est_duration,
    }


def mark_patient_seen(record_id: int) -> dict[str, Any]:
    _build_db_manager().mark_patient_seen(record_id)
    return {"record_id": record_id, "status": "seen"}


def delete_queue_record(record_id: int) -> dict[str, Any]:
    _build_db_manager().delete_queue_record(record_id)
    return {"record_id": record_id, "status": "deleted"}


def update_patient_triage(record_id: int, priority: int, est_duration: int) -> dict[str, Any]:
    _build_db_manager().update_patient_triage(record_id, priority, est_duration)
    return {
        "record_id": record_id,
        "priority": priority,
        "est_duration": est_duration,
        "status": "updated",
    }


def collect_data(days_to_simulate: int, num_doctors: int, persist_to_db: bool) -> dict[str, Any]:
    synthetic_module = _load_module("queuecontrol_clinical_annual_visits", SYNTHETIC_DATA_SCRIPT_PATH)
    config = synthetic_module.ClinicalAnnualVisitsConfig(
        days_to_simulate=days_to_simulate,
        num_doctors=num_doctors,
    )
    generator = synthetic_module.ClinicalAnnualVisitsGenerator(config=config, app_logger=logger)
    dataset = generator.generate_data(persist_to_db=persist_to_db)
    return {
        "status": "ok",
        "persisted_to_db": persist_to_db,
        "rows": int(len(dataset)),
        "clinics": int(dataset["clinic_id"].nunique()) if not dataset.empty else 0,
        "start_at": _to_python(dataset["arrival_time"].min()) if not dataset.empty else None,
        "end_at": _to_python(dataset["arrival_time"].max()) if not dataset.empty else None,
        "preview": dataframe_to_records(dataset.head(5)),
    }


def _load_training_data() -> pd.DataFrame:
    return _build_db_manager().fetch_training_data("clinic_historical_data")


def run_eda() -> dict[str, Any]:
    training_df = _load_training_data()
    missing_counts = {
        column: int(count)
        for column, count in training_df.isna().sum().items()
        if int(count) > 0
    }

    return {
        "status": "ok",
        "rows": int(len(training_df)),
        "columns": list(training_df.columns),
        "clinic_count": int(training_df["clinic_id"].nunique()) if "clinic_id" in training_df.columns else 0,
        "start_at": _to_python(training_df["arrival_time"].min()) if "arrival_time" in training_df.columns else None,
        "end_at": _to_python(training_df["arrival_time"].max()) if "arrival_time" in training_df.columns else None,
        "surge_rate": float(training_df["is_surge_imminent"].mean()) if "is_surge_imminent" in training_df.columns else None,
        "avg_wait_minutes": float(training_df["actual_wait_minutes"].mean()) if "actual_wait_minutes" in training_df.columns else None,
        "avg_queue_length": float(training_df["queue_length_at_arrival"].mean()) if "queue_length_at_arrival" in training_df.columns else None,
        "missing_counts": missing_counts,
    }


def preprocess(model_type: str) -> dict[str, Any]:
    resolved_model_type = _normalize_model_type(model_type)
    training_df = _load_training_data().replace([np.inf, -np.inf], np.nan)

    if resolved_model_type == "rush-hour":
        required_columns = [*RUSH_HOUR_FEATURES, "is_surge_imminent"]
        prepared_df = training_df[required_columns].dropna(subset=["is_surge_imminent"])
        target_counts = prepared_df["is_surge_imminent"].astype(int).value_counts().to_dict()
    else:
        required_columns = [*WAIT_TIME_FEATURES, "actual_wait_minutes"]
        prepared_df = training_df[required_columns].dropna()
        target_counts = {
            "min": float(prepared_df["actual_wait_minutes"].min()) if not prepared_df.empty else None,
            "median": float(prepared_df["actual_wait_minutes"].median()) if not prepared_df.empty else None,
            "max": float(prepared_df["actual_wait_minutes"].max()) if not prepared_df.empty else None,
        }

    return {
        "status": "ok",
        "model_type": resolved_model_type,
        "rows": int(len(prepared_df)),
        "columns": list(prepared_df.columns),
        "missing_values_after_preprocess": int(prepared_df.isna().sum().sum()),
        "target_summary": {str(key): _to_python(value) for key, value in target_counts.items()},
        "preview": dataframe_to_records(prepared_df.head(5)),
    }


def _artifact_paths_for_model(model_type: str) -> tuple[Path, Path]:
    if _normalize_model_type(model_type) == "rush-hour":
        return RUSH_HOUR_MODEL_PATH, RUSH_HOUR_METRICS_PATH
    return WAIT_TIME_MODEL_PATH, WAIT_TIME_METRICS_PATH


def train_model(model_type: str) -> dict[str, Any]:
    resolved_model_type = _normalize_model_type(model_type)
    if resolved_model_type == "rush-hour":
        module = _load_module("queuecontrol_rush_hour_predictor", RUSH_HOUR_SCRIPT_PATH)
    else:
        module = _load_module("queuecontrol_wait_time_predictor", WAIT_TIME_SCRIPT_PATH)

    module.train_model()
    return validate_model(resolved_model_type)


def validate_model(model_type: str) -> dict[str, Any]:
    resolved_model_type = _normalize_model_type(model_type)
    model_path, metrics_path = _artifact_paths_for_model(resolved_model_type)
    metrics = _load_json_file(metrics_path)
    return {
        "status": "ready" if model_path.exists() else "missing",
        "model_type": resolved_model_type,
        "available": model_path.exists(),
        "artifact_path": str(model_path),
        "metrics_path": str(metrics_path),
        "metrics": metrics,
        "trained_at": metrics.get("trained_at"),
    }


def predict_surge(
    queue_records: list[dict[str, Any]] | None = None,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    model = _load_rush_hour_model()
    if model is None:
        raise FileNotFoundError("Rush-hour model artifact is missing. Train the model before requesting predictions.")

    queue_df = queue_records_to_df(queue_records or get_waiting_queue())
    now = current_time or datetime.now()
    recent_patients = queue_df[queue_df["arrival_time"] >= (now - pd.Timedelta(hours=1))] if not queue_df.empty else queue_df
    avg_wait_last_hour = 0.0
    if not recent_patients.empty:
        avg_wait_last_hour = float(((now - recent_patients["arrival_time"]).dt.total_seconds() / 60.0).mean())

    hour_of_day = now.hour
    day_of_week = now.weekday()
    features = pd.DataFrame([
        {
            "is_weekend": int(day_of_week >= 5),
            "day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
            "day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
            "hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
            "hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
            "queue_length_at_arrival": len(queue_df),
            "arrivals_last_1_hour": len(recent_patients),
            "avg_wait_last_1_hour": avg_wait_last_hour,
        }
    ])
    probability = float(model.predict_proba(features)[0][1])
    return {
        "status": "ok",
        "probability": round(probability, 4),
        "generated_at": now.isoformat(),
        "queue_size": int(len(queue_df)),
    }


def predict_wait_time(
    clinic_name: str,
    queue_records: list[dict[str, Any]] | None = None,
    current_time: datetime | None = None,
    doctor_count: int | None = None,
) -> dict[str, Any]:
    bundle = _load_wait_time_model()
    if bundle is None:
        raise FileNotFoundError("Wait-time model artifact is missing. Train the model before requesting predictions.")

    db_manager = _build_db_manager()
    clinics_df = db_manager.fetch_clinics()
    clinic_id_by_name = dict(zip(clinics_df["clinic_name"], clinics_df["clinic_id"]))
    clinic_id = clinic_id_by_name.get(clinic_name)
    if not clinic_id:
        raise ValueError(f"Unknown clinic '{clinic_name}'.")

    if queue_records:
        clinic_df = queue_records_to_df(queue_records)
    else:
        full_queue = queue_records_to_df(get_waiting_queue())
        clinic_df = full_queue[full_queue["clinic_name"] == clinic_name].copy()

    now = current_time or datetime.now()
    recent_df = clinic_df[clinic_df["arrival_time"] >= (now - pd.Timedelta(hours=1))] if not clinic_df.empty else clinic_df

    avg_wait_last_hour = 0.0
    if not recent_df.empty:
        avg_wait_last_hour = float(((now - recent_df["arrival_time"]).dt.total_seconds() / 60.0).mean())
    elif not clinic_df.empty:
        avg_wait_last_hour = float(((now - clinic_df["arrival_time"]).dt.total_seconds() / 60.0).mean())

    feature_row = pd.DataFrame([
        {
            "clinic_id": clinic_id,
            "is_weekend": int(now.weekday() >= 5),
            "day_sin": np.sin(2 * np.pi * now.weekday() / 7.0),
            "day_cos": np.cos(2 * np.pi * now.weekday() / 7.0),
            "hour_sin": np.sin(2 * np.pi * now.hour / 24.0),
            "hour_cos": np.cos(2 * np.pi * now.hour / 24.0),
            "queue_length_at_arrival": len(clinic_df),
            "arrivals_last_1_hour": float(len(recent_df)),
            "avg_wait_last_1_hour": avg_wait_last_hour,
        }
    ])
    encoded_row = pd.get_dummies(feature_row, columns=["clinic_id"], prefix="clinic")
    encoded_row = encoded_row.reindex(columns=list(bundle.get("feature_columns", [])), fill_value=0.0)

    predicted_p50 = max(0.0, float(bundle["model"].predict(encoded_row)[0]))
    clinic_uplifts = bundle.get("clinic_p90_uplift_minutes", {})
    global_uplift = float(bundle.get("global_p90_uplift_minutes", 0.0))
    predicted_p90 = max(predicted_p50, predicted_p50 + float(clinic_uplifts.get(clinic_id, global_uplift)))

    metrics = _load_json_file(WAIT_TIME_METRICS_PATH)
    baseline_doctors = max(1, int(metrics.get("historical_num_doctors", 2) or 2))
    current_doctors = max(1, int(doctor_count or baseline_doctors))
    staffing_factor = baseline_doctors / current_doctors

    predicted_p50 *= staffing_factor
    predicted_p90 = max(predicted_p50, predicted_p90 * staffing_factor)

    return {
        "status": "ok",
        "clinic_name": clinic_name,
        "doctor_count": current_doctors,
        "p50_minutes": round(predicted_p50, 2),
        "p90_minutes": round(predicted_p90, 2),
        "generated_at": now.isoformat(),
    }