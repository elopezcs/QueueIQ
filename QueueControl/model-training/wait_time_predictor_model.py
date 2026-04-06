import heapq
import json
import os
import sys
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_pinball_loss
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

from database.database_manager import DatabaseManager

TABLE_NAME = "clinic_historical_data"
FEATURE_COLUMNS = [
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
TARGET = "actual_wait_minutes"
MODEL_PATH = os.path.abspath(
	os.path.join(os.path.dirname(__file__), "..", "models", "wait_time_predictor_model.joblib")
)
METRICS_PATH = os.path.abspath(
	os.path.join(os.path.dirname(__file__), "..", "models", "wait_time_predictor_metrics.json")
)


def _build_db_manager() -> DatabaseManager:
	manager = DatabaseManager()
	manager.init_db()
	return manager


def _encode_features(df: pd.DataFrame) -> pd.DataFrame:
	feature_df = df[FEATURE_COLUMNS].copy()
	return pd.get_dummies(feature_df, columns=["clinic_id"], prefix="clinic")


def _build_neural_network_regressor() -> Pipeline:
	return Pipeline([
		("imputer", SimpleImputer(strategy="median")),
		("scaler", StandardScaler()),
		(
			"regressor",
			MLPRegressor(
				hidden_layer_sizes=(64, 32),
				activation="relu",
				solver="adam",
				alpha=1e-4,
				batch_size=32,
				learning_rate_init=1e-3,
				max_iter=500,
				early_stopping=True,
				validation_fraction=0.1,
				n_iter_no_change=20,
				random_state=42,
			),
		),
	])


def _compute_clinic_residual_uplifts(
	feature_frame: pd.DataFrame,
	target: pd.Series,
	predictions: np.ndarray,
	clinic_ids: pd.Series,
) -> tuple[dict[str, float], float]:
	residual_df = pd.DataFrame({
		"clinic_id": clinic_ids.astype(str).values,
		"residual": np.maximum(target.to_numpy() - predictions, 0.0),
	})
	clinic_uplifts = residual_df.groupby("clinic_id")["residual"].quantile(0.9).to_dict()
	global_uplift = float(np.quantile(residual_df["residual"].to_numpy(), 0.9)) if not residual_df.empty else 0.0
	return ({clinic_id: float(value) for clinic_id, value in clinic_uplifts.items()}, global_uplift)


def _build_training_data_from_queue_activity(db_manager: DatabaseManager) -> pd.DataFrame:
	activity_df = db_manager.fetch_queue_activity()
	if activity_df.empty or "seen_by_doctor_time" not in activity_df.columns:
		raise ValueError("Queue activity is empty. Historical data generation is required before training.")

	clinics_df = db_manager.fetch_clinics()
	clinic_id_by_name = dict(zip(clinics_df["clinic_name"], clinics_df["clinic_id"]))

	fallback_df = activity_df.copy()
	fallback_df["arrival_time"] = pd.to_datetime(fallback_df["arrival_time"])
	fallback_df["seen_by_doctor_time"] = pd.to_datetime(fallback_df["seen_by_doctor_time"])
	fallback_df["clinic_id"] = fallback_df["clinic_name"].map(clinic_id_by_name)
	fallback_df = fallback_df[
		fallback_df["clinic_id"].notna() & fallback_df["seen_by_doctor_time"].notna()
	].copy()

	if fallback_df.empty:
		raise ValueError("Queue activity does not contain completed patient records for wait-time training.")

	fallback_df["actual_wait_minutes"] = (
		(fallback_df["seen_by_doctor_time"] - fallback_df["arrival_time"]).dt.total_seconds() / 60.0
	).clip(lower=0.0)
	fallback_df["day_of_week"] = fallback_df["arrival_time"].dt.weekday
	fallback_df["is_weekend"] = (fallback_df["day_of_week"] >= 5).astype(int)
	fallback_df["hour_of_day"] = fallback_df["arrival_time"].dt.hour
	fallback_df["hour_sin"] = np.sin(2 * np.pi * fallback_df["hour_of_day"] / 24.0)
	fallback_df["hour_cos"] = np.cos(2 * np.pi * fallback_df["hour_of_day"] / 24.0)
	fallback_df["day_sin"] = np.sin(2 * np.pi * fallback_df["day_of_week"] / 7.0)
	fallback_df["day_cos"] = np.cos(2 * np.pi * fallback_df["day_of_week"] / 7.0)

	fallback_df = fallback_df.sort_values(by=["clinic_id", "arrival_time"]).reset_index(drop=True)

	queue_lengths: list[int] = []
	for _, clinic_df in fallback_df.groupby("clinic_id", sort=False):
		active_departures: list[datetime] = []
		for row in clinic_df.itertuples(index=False):
			arrival_time = pd.Timestamp(row.arrival_time).to_pydatetime()
			while active_departures and active_departures[0] <= arrival_time:
				heapq.heappop(active_departures)
			queue_lengths.append(len(active_departures))
			heapq.heappush(
				active_departures,
				pd.Timestamp(row.seen_by_doctor_time).to_pydatetime(),
			)

	fallback_df["queue_length_at_arrival"] = queue_lengths
	fallback_df = fallback_df.set_index("arrival_time")

	arrivals_last_hour: list[float] = []
	avg_wait_last_hour: list[float] = []
	for _, clinic_df in fallback_df.groupby("clinic_id", sort=False):
		arrivals_last_hour.extend(
			clinic_df["clinic_id"].rolling("1h", closed="left").count().fillna(0.0).tolist()
		)
		avg_wait_last_hour.extend(
			clinic_df[TARGET].rolling("1h", closed="left").mean().fillna(0.0).tolist()
		)

	fallback_df = fallback_df.reset_index()
	fallback_df["arrivals_last_1_hour"] = arrivals_last_hour
	fallback_df["avg_wait_last_1_hour"] = avg_wait_last_hour

	return fallback_df[[*FEATURE_COLUMNS, TARGET]].replace([np.inf, -np.inf], np.nan).dropna()


def _fetch_training_data(db_manager: DatabaseManager) -> tuple[pd.DataFrame, str]:
	try:
		historical_df = db_manager.fetch_training_data(TABLE_NAME)
		required_columns = [*FEATURE_COLUMNS, TARGET]
		if all(column in historical_df.columns for column in required_columns):
			training_df = historical_df[required_columns].replace([np.inf, -np.inf], np.nan).dropna()
			if not training_df.empty:
				return training_df, TABLE_NAME
	except Exception:
		pass

	return _build_training_data_from_queue_activity(db_manager), "clinic_queue"


def train_model() -> None:
	db_manager = _build_db_manager()
	print("Loading wait-time training data...")
	training_df, source_table = _fetch_training_data(db_manager)

	if training_df.empty:
		raise ValueError("No usable training rows were available for the wait-time predictor.")

	encoded_features = _encode_features(training_df)
	target = training_df[TARGET].astype(float)
	clinic_ids = training_df["clinic_id"].astype(str)

	X_train, X_test, y_train, y_test = train_test_split(
		encoded_features,
		target,
		test_size=0.2,
		random_state=42,
	)
	clinic_train, clinic_test = train_test_split(
		clinic_ids,
		test_size=0.2,
		random_state=42,
	)

	model_p50 = _build_neural_network_regressor()

	print(f"Training wait-time models from {source_table}...")
	model_p50.fit(X_train, y_train)

	pred_p50 = np.clip(model_p50.predict(X_test), a_min=0.0, a_max=None)
	train_pred_p50 = np.clip(model_p50.predict(X_train), a_min=0.0, a_max=None)
	clinic_uplifts, global_uplift = _compute_clinic_residual_uplifts(X_train, y_train, train_pred_p50, clinic_train)
	pred_p90 = np.array([
		max(pred, pred + clinic_uplifts.get(clinic_id, global_uplift))
		for pred, clinic_id in zip(pred_p50, clinic_test)
	])

	p50_mae = mean_absolute_error(y_test, pred_p50)
	p50_pinball = mean_pinball_loss(y_test, pred_p50, alpha=0.5)
	p90_pinball = mean_pinball_loss(y_test, pred_p90, alpha=0.9)
	p90_coverage = float((y_test <= pred_p90).mean())

	print("\nWait-Time Model Evaluation:")
	print(f"P50 MAE: {p50_mae:.2f} minutes")
	print(f"P50 pinball loss: {p50_pinball:.2f}")
	print(f"P90 pinball loss: {p90_pinball:.2f}")
	print(f"P90 coverage: {p90_coverage:.3f}")

	os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
	bundle = {
		"model": model_p50,
		"model_family": "neural_network",
		"clinic_p90_uplift_minutes": clinic_uplifts,
		"global_p90_uplift_minutes": float(global_uplift),
		"feature_columns": list(encoded_features.columns),
		"input_columns": FEATURE_COLUMNS,
		"target_column": TARGET,
		"trained_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
		"training_source": source_table,
	}
	joblib.dump(bundle, MODEL_PATH)

	metrics_payload = {
		"training_source": source_table,
		"rows": int(len(training_df)),
		"train_size": int(len(y_train)),
		"test_size": int(len(y_test)),
		"p50_mae_minutes": float(p50_mae),
		"p50_pinball_loss": float(p50_pinball),
		"p90_pinball_loss": float(p90_pinball),
		"p90_coverage": p90_coverage,
		"model_family": "neural_network",
		"historical_num_doctors": 2,
		"trained_at": bundle["trained_at"],
	}
	with open(METRICS_PATH, "w", encoding="utf-8") as metrics_file:
		json.dump(metrics_payload, metrics_file, indent=2)

	print(f"Wait-time predictor saved successfully to {MODEL_PATH}")
	print(f"Wait-time metrics saved successfully to {METRICS_PATH}")


if __name__ == "__main__":
	train_model()
