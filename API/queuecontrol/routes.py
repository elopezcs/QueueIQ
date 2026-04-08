from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from API.queuecontrol import services
from API.queuecontrol.schemas import (
    CollectDataRequest,
    PredictSurgeRequest,
    PredictWaitTimeRequest,
    QueuePatientCreateRequest,
    QueueTriageUpdateRequest,
)

router = APIRouter(tags=["queuecontrol"])


@router.get("/queuecontrol/health-status")
def queuecontrol_health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/queuecontrol/collect-synthetic-historical-data")
def collect_data(payload: CollectDataRequest) -> dict[str, object]:
    try:
        return services.collect_data(
            days_to_simulate=payload.days_to_simulate,
            num_doctors=payload.num_doctors,
            persist_to_db=payload.persist_to_db,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/queuecontrol/run-historical-data-eda")
def run_eda() -> dict[str, object]:
    try:
        return services.run_eda()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/preprocess-rush-hour-predictor-model-training-data")
def preprocess_rush_hour_predictor_model_training_data() -> dict[str, object]:
    try:
        return services.preprocess("rush-hour")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/preprocess-wait-time-predictor-model-training-data")
def preprocess_wait_time_predictor_model_training_data() -> dict[str, object]:
    try:
        return services.preprocess("wait-time")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/train-rush-hour-predictor-model")
def train_rush_hour_predictor_model() -> dict[str, object]:
    try:
        return services.train_model("rush-hour")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/train-wait-time-predictor-model")
def train_wait_time_predictor_model() -> dict[str, object]:
    try:
        return services.train_model("wait-time")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/queuecontrol/validate-rush-hour-predictor-model-artifacts")
def validate_rush_hour_predictor_model_artifacts() -> dict[str, object]:
    try:
        return services.validate_model("rush-hour")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/queuecontrol/validate-wait-time-predictor-model-artifacts")
def validate_wait_time_predictor_model_artifacts() -> dict[str, object]:
    try:
        return services.validate_model("wait-time")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/predict-rush-hour-predictor-model-surge")
def predict_rush_hour_predictor_model_surge(payload: PredictSurgeRequest) -> dict[str, object]:
    try:
        return services.predict_surge(
            queue_records=[record.model_dump(mode="json") for record in payload.queue_records],
            current_time=payload.current_time,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/predict-wait-time-predictor-model-estimate")
def predict_wait_time_predictor_model_estimate(payload: PredictWaitTimeRequest) -> dict[str, object]:
    try:
        return services.predict_wait_time(
            clinic_name=payload.clinic_name,
            queue_records=[record.model_dump(mode="json") for record in payload.queue_records],
            current_time=payload.current_time,
            doctor_count=payload.doctor_count,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/queuecontrol/list-registered-clinics")
def get_clinics() -> dict[str, object]:
    return {"status": "ok", "clinics": services.get_clinics()}


@router.get("/queuecontrol/list-active-queue-records")
def get_queue() -> dict[str, object]:
    return {"status": "ok", "records": services.get_waiting_queue()}


@router.get("/queuecontrol/list-queue-activity-history")
def get_queue_activity() -> dict[str, object]:
    return {"status": "ok", "records": services.get_queue_activity()}


@router.post("/queuecontrol/create-queue-patient-record", status_code=status.HTTP_201_CREATED)
def add_queue_patient(payload: QueuePatientCreateRequest) -> dict[str, object]:
    try:
        est_duration = payload.est_duration if payload.est_duration is not None else services.get_duration(payload.priority)
        patient = services.add_queue_patient(
            clinic_name=payload.clinic_name,
            patient_id=payload.patient_id,
            arrival_time=payload.arrival_time,
            priority=payload.priority,
            est_duration=est_duration,
            chat_session_id=payload.chat_session_id,
        )
        return {"status": "ok", "patient": patient}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/queuecontrol/queue-patient-records/{record_id}/mark-as-seen")
def mark_queue_patient_seen(record_id: int) -> dict[str, object]:
    try:
        return services.mark_patient_seen(record_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.patch("/queuecontrol/queue-patient-records/{record_id}/update-triage")
def update_queue_patient_triage(record_id: int, payload: QueueTriageUpdateRequest) -> dict[str, object]:
    try:
        est_duration = payload.est_duration if payload.est_duration is not None else {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[payload.priority]
        return services.update_patient_triage(record_id, payload.priority, est_duration)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.delete("/queuecontrol/queue-patient-records/{record_id}/remove")
def delete_queue_patient(record_id: int) -> dict[str, object]:
    try:
        return services.delete_queue_record(record_id)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc