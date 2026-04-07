from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib import error, parse, request

import pandas as pd


def _json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, pd.DataFrame):
        return [
            {column: _json_ready(cell) for column, cell in row.items()}
            for row in value.where(pd.notna(value), None).to_dict(orient="records")
        ]
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


class QueueControlApiClient:
    def __init__(self, base_url: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = (base_url or os.getenv("QUEUECONTROL_API_BASE_URL") or os.getenv("QUEUEIQ_API_BASE_URL") or "http://127.0.0.1:8000").rstrip("/")
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            clean_query = {key: value for key, value in query.items() if value is not None}
            if clean_query:
                url = f"{url}?{parse.urlencode(clean_query)}"

        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(_json_ready(payload)).encode("utf-8")

        http_request = request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                raw_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"QueueControl API request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"QueueControl API is unavailable at {self.base_url}: {exc.reason}") from exc

        return json.loads(raw_body) if raw_body else {}

    @staticmethod
    def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame(records)
        for column in ("arrival_time", "seen_by_doctor_time"):
            if column in df.columns:
                df[column] = pd.to_datetime(df[column], errors="coerce")
        return df

    @staticmethod
    def _normalize_model_type(model_type: str) -> str:
        normalized = model_type.strip().lower()
        if normalized not in {"rush-hour", "wait-time"}:
            raise ValueError("model_type must be either 'rush-hour' or 'wait-time'.")
        return normalized

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/queuecontrol/health-status")

    def collect_data(self, *, days_to_simulate: int = 365, num_doctors: int = 2, persist_to_db: bool = True) -> dict[str, Any]:
        return self._request(
            "POST",
            "/queuecontrol/collect-synthetic-historical-data",
            payload={
                "days_to_simulate": days_to_simulate,
                "num_doctors": num_doctors,
                "persist_to_db": persist_to_db,
            },
        )

    def run_eda(self) -> dict[str, Any]:
        return self._request("GET", "/queuecontrol/run-historical-data-eda")

    def preprocess(self, model_type: str) -> dict[str, Any]:
        normalized_model_type = self._normalize_model_type(model_type)
        endpoint_path = (
            "/queuecontrol/preprocess-rush-hour-predictor-model-training-data"
            if normalized_model_type == "rush-hour"
            else "/queuecontrol/preprocess-wait-time-predictor-model-training-data"
        )
        return self._request("POST", endpoint_path)

    def train_model(self, model_type: str) -> dict[str, Any]:
        normalized_model_type = self._normalize_model_type(model_type)
        endpoint_path = (
            "/queuecontrol/train-rush-hour-predictor-model"
            if normalized_model_type == "rush-hour"
            else "/queuecontrol/train-wait-time-predictor-model"
        )
        return self._request("POST", endpoint_path)

    def validate_model(self, model_type: str) -> dict[str, Any]:
        normalized_model_type = self._normalize_model_type(model_type)
        endpoint_path = (
            "/queuecontrol/validate-rush-hour-predictor-model-artifacts"
            if normalized_model_type == "rush-hour"
            else "/queuecontrol/validate-wait-time-predictor-model-artifacts"
        )
        return self._request("GET", endpoint_path)

    def predict_surge(self, queue_records: pd.DataFrame | list[dict[str, Any]] | None = None, *, current_time: datetime | None = None) -> dict[str, Any]:
        records = queue_records
        if isinstance(queue_records, pd.DataFrame):
            records = _json_ready(queue_records)
        return self._request(
            "POST",
            "/queuecontrol/predict-rush-hour-predictor-model-surge",
            payload={
                "queue_records": records or [],
                "current_time": current_time,
            },
        )

    def predict_wait_time(
        self,
        clinic_name: str,
        queue_records: pd.DataFrame | list[dict[str, Any]] | None = None,
        *,
        current_time: datetime | None = None,
        doctor_count: int | None = None,
    ) -> dict[str, Any]:
        records = queue_records
        if isinstance(queue_records, pd.DataFrame):
            records = _json_ready(queue_records)
        return self._request(
            "POST",
            "/queuecontrol/predict-wait-time-predictor-model-estimate",
            payload={
                "clinic_name": clinic_name,
                "queue_records": records or [],
                "current_time": current_time,
                "doctor_count": doctor_count,
            },
        )

    def get_clinics(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/queuecontrol/list-registered-clinics").get("clinics", []))

    def get_clinics_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.get_clinics())

    def get_queue(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/queuecontrol/list-active-queue-records").get("records", []))

    def get_queue_df(self) -> pd.DataFrame:
        return self.records_to_dataframe(self.get_queue())

    def get_queue_activity(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/queuecontrol/list-queue-activity-history").get("records", []))

    def get_queue_activity_df(self) -> pd.DataFrame:
        return self.records_to_dataframe(self.get_queue_activity())

    def add_patient(
        self,
        clinic_name: str,
        patient_id: int,
        arrival_time: datetime,
        priority: int,
        est_duration: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/queuecontrol/create-queue-patient-record",
            payload={
                "clinic_name": clinic_name,
                "patient_id": patient_id,
                "arrival_time": arrival_time,
                "priority": priority,
                "est_duration": est_duration,
            },
        )

    def mark_patient_seen(self, record_id: int) -> dict[str, Any]:
        return self._request("POST", f"/queuecontrol/queue-patient-records/{record_id}/mark-as-seen")

    def update_patient_triage(self, record_id: int, priority: int, est_duration: int | None = None) -> dict[str, Any]:
        return self._request(
            "PATCH",
            f"/queuecontrol/queue-patient-records/{record_id}/update-triage",
            payload={"priority": priority, "est_duration": est_duration},
        )

    def delete_queue_record(self, record_id: int) -> dict[str, Any]:
        return self._request("DELETE", f"/queuecontrol/queue-patient-records/{record_id}/remove")