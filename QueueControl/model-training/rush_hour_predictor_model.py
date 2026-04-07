import pandas as pd
import numpy as np
import json
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from QueueControl.api_client import QueueControlApiClient

# -----------------------------
# DATABASE & ENVIRONMENT
# -----------------------------
from database.database_manager import DatabaseManager
try:
    db_manager = DatabaseManager()
    db_manager.init_db()
except Exception as e:
    print(f"**❌ Failed to connect to the database:** {e}")
    exit(1)

from dotenv import load_dotenv

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=_ENV_PATH, override=True)

DEFAULT_FEATURES = [
    "is_weekend", "day_sin", "day_cos", "hour_sin", "hour_cos",
    "queue_length_at_arrival", "arrivals_last_1_hour", "avg_wait_last_1_hour"
]
FEATURES_ENV = os.getenv("RUSH_HOUR_MODEL_FEATURES")
FEATURES = [feature.strip() for feature in FEATURES_ENV.split(",")] if FEATURES_ENV else DEFAULT_FEATURES
TARGET = os.getenv("RUSH_HOUR_MODEL_TARGET", "is_surge_imminent")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_NAME = "clinic_historical_data"
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_model.joblib")
)
MODEL_METRICS_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_metrics.json")
)
SYNTHETIC_DATA_SCRIPT_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "synthetic-data-generation", "clinical_annual_visits.py")
)


def remove_existing_model():
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        print(f"Deleted existing model at {MODEL_PATH}")


def _should_generate_synthetic_data(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return "is empty" in error_text or "does not exist" in error_text or "undefinedtable" in error_text


def _run_synthetic_data_script() -> None:
    print(
        "Training data does not exist. Synthetic data needs to be generated before proceeding with training the model."
    )
    print(f"Running synthetic data generator: {SYNTHETIC_DATA_SCRIPT_PATH}")

    try:
        completed_process = subprocess.run(
            [sys.executable, SYNTHETIC_DATA_SCRIPT_PATH],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_details = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise RuntimeError(
            f"Failed to generate synthetic data before training. Original error: {error_details}"
        ) from exc

    if completed_process.stdout.strip():
        print(completed_process.stdout.strip())
    if completed_process.stderr.strip():
        print(completed_process.stderr.strip())


def _fetch_or_generate_training_data() -> pd.DataFrame:
    try:
        return db_manager.fetch_training_data(TABLE_NAME)
    except Exception as exc:
        if not _should_generate_synthetic_data(exc):
            raise

        _run_synthetic_data_script()
        return db_manager.fetch_training_data(TABLE_NAME)


def train_model():
    print(f"Loading training data from database table '{TABLE_NAME}'...")
    df = _fetch_or_generate_training_data()

    # 1. Define Features (X) and Target (y)
    training_df = df[FEATURES + [TARGET]].replace([np.inf, -np.inf], np.nan)
    training_df = training_df.dropna(subset=[TARGET])

    X = training_df[FEATURES]
    y = training_df[TARGET].astype(int)

    if y.nunique() < 2:
        raise ValueError("Training data must contain both surge and non-surge examples.")

    # 2. Train/Test Split (80% training, 20% testing)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("Training neural network classifier...")
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        (
            "classifier",
            MLPClassifier(
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

    model.fit(X_train, y_train)

    # 3. Evaluate the Model
    print("\nModel Evaluation:")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)
    report = classification_report(y_test, y_pred, zero_division=0, output_dict=True)

    print(f"Accuracy: {accuracy:.4f}")
    print(f"ROC-AUC Score: {roc_auc:.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, zero_division=0))

    # 4. Save the Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    remove_existing_model()
    joblib.dump(model, MODEL_PATH)
    metrics_payload = {
        "accuracy": float(accuracy),
        "roc_auc": float(roc_auc),
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "positive_precision": float(report.get("1", {}).get("precision", 0.0)),
        "positive_recall": float(report.get("1", {}).get("recall", 0.0)),
        "positive_f1": float(report.get("1", {}).get("f1-score", 0.0)),
        "trained_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    with open(MODEL_METRICS_PATH, "w", encoding="utf-8") as metrics_file:
        json.dump(metrics_payload, metrics_file, indent=2)
    print(f"Neural network model saved successfully to {MODEL_PATH}")
    print(f"Model evaluation metrics saved successfully to {MODEL_METRICS_PATH}")

if __name__ == "__main__":
    response = QueueControlApiClient().train_model("rush-hour")
    print(json.dumps(response, indent=2))