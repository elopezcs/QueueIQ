import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
import importlib.util
import os
import re
import subprocess
import sys
import logging

logger = logging.getLogger("queueiq.api")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)   

# -----------------------------
# DATABASE & ENVIRONMENT
# -----------------------------
from database.database_manager import DatabaseManager
try:
    db_manager = DatabaseManager()
    db_manager.init_db()
except Exception as e:
    logger.error(f"**❌ Failed to connect to the database:** {e}")
    exit(1)

from dotenv import load_dotenv

_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=_ENV_PATH, override=True)

DEFAULT_FEATURES = [
    "is_weekend", "day_sin", "day_cos", "hour_sin", "hour_cos",
    "queue_length_at_arrival", "arrivals_last_1_hour", "avg_wait_last_1_hour"
]


def parse_env_list(raw_value: str | None, default: list[str]) -> list[str]:
    if not raw_value:
        return default

    cleaned_value = raw_value.strip()
    if cleaned_value in {"[", "]", "[]"}:
        return default

    if cleaned_value.startswith("[") and cleaned_value.endswith("]"):
        cleaned_value = cleaned_value[1:-1]

    values = []
    for item in re.split(r",|\r?\n", cleaned_value):
        normalized_item = item.strip().strip('"').strip("'").strip("[]").strip()
        if normalized_item:
            values.append(normalized_item)

    return values or default


def parse_env_int(raw_value: str | None, default: int) -> int:
    if not raw_value:
        return default
    return int(raw_value.strip().strip('"').strip("'"))


def parse_env_float(raw_value: str | None, default: float) -> float:
    if not raw_value:
        return default
    return float(raw_value.strip().strip('"').strip("'"))


def parse_env_bool(raw_value: str | None, default: bool) -> bool:
    if not raw_value:
        return default

    normalized_value = raw_value.strip().strip('"').strip("'").lower()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False
    return default


def parse_env_int_tuple(raw_value: str | None, default: tuple[int, ...]) -> tuple[int, ...]:
    values = parse_env_list(raw_value, [str(value) for value in default])
    return tuple(int(value) for value in values)


FEATURES_ENV = os.getenv("RUSH_HOUR_MODEL_FEATURES")
FEATURES = parse_env_list(FEATURES_ENV, DEFAULT_FEATURES)
TARGET = os.getenv("RUSH_HOUR_MODEL_TARGET", "is_surge_imminent").strip().strip('"').strip("'")
HIDDEN_LAYER_SIZES = parse_env_int_tuple(os.getenv("RUSH_HOUR_MODEL_HIDDEN_LAYER_SIZES"), (64, 32))
ACTIVATION = os.getenv("RUSH_HOUR_MODEL_ACTIVATION", "relu").strip().strip('"').strip("'")
SOLVER = os.getenv("RUSH_HOUR_MODEL_SOLVER", "adam").strip().strip('"').strip("'")
ALPHA = parse_env_float(os.getenv("RUSH_HOUR_MODEL_ALPHA"), 1e-4)
BATCH_SIZE = parse_env_int(os.getenv("RUSH_HOUR_MODEL_BATCH_SIZE"), 32)
LEARNING_RATE_INIT = parse_env_float(os.getenv("RUSH_HOUR_MODEL_LEARNING_RATE_INIT"), 1e-3)
EPOCHS = parse_env_int(os.getenv("RUSH_HOUR_MODEL_EPOCHS"), 500)
EARLY_STOPPING = parse_env_bool(os.getenv("RUSH_HOUR_MODEL_EARLY_STOPPING"), True)
VALIDATION_FRACTION = parse_env_float(os.getenv("RUSH_HOUR_MODEL_VALIDATION_FRACTION"), 0.1)
N_ITER_NO_CHANGE = parse_env_int(os.getenv("RUSH_HOUR_MODEL_N_ITER_NO_CHANGE"), 20)
MODEL_RANDOM_STATE = parse_env_int(os.getenv("RUSH_HOUR_MODEL_RANDOM_STATE"), 42)
EXPECTED_ACCURACY = parse_env_float(os.getenv("RUSH_HOUR_MODEL_EXPECTED_ACCURACY"), 0.80)
EXPECTED_ROC_AUC = parse_env_float(os.getenv("RUSH_HOUR_MODEL_EXPECTED_ROC_AUC"), 0.85)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_NAME = "clinic_historical_data"
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_model.joblib")
)
SYNTHETIC_DATA_SCRIPT_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "synthetic-data-generation", "clinical_annual_visits.py")
)


def remove_existing_model():
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        logger.info(f"🗑️ Deleted existing model at {MODEL_PATH}")


def _should_generate_synthetic_data(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return "is empty" in error_text or "does not exist" in error_text or "undefinedtable" in error_text


def _run_synthetic_data_script() -> None:
    logger.warning(
        "Training data does not exist. Synthetic data needs to be generated before proceeding with model training."
    )
    logger.info(f"Running synthetic data generator at {SYNTHETIC_DATA_SCRIPT_PATH}...")

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
        logger.info(completed_process.stdout.strip())
    if completed_process.stderr.strip():
        logger.warning(completed_process.stderr.strip())


def _fetch_or_generate_training_data() -> pd.DataFrame:
    try:
        return db_manager.fetch_training_data(TABLE_NAME)
    except Exception as exc:
        if not _should_generate_synthetic_data(exc):
            error_message = (
                f"❌ Database or training table '{TABLE_NAME}' could not be loaded. "
                f"Original error: {exc}"
            )
            logger.error(error_message)
            raise RuntimeError(error_message) from exc

        _run_synthetic_data_script()
        return db_manager.fetch_training_data(TABLE_NAME)


def train_model():
    logger.info(f"📥 Loading training data from database table '{TABLE_NAME}'...")
    df = _fetch_or_generate_training_data()

    # 1. Define Features (X) and Target (y)
    missing_columns = [column for column in FEATURES + [TARGET] if column not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Configured feature/target columns are missing from training data: {missing_columns}. "
            f"Available columns: {list(df.columns)}"
        )

    training_df = df[FEATURES + [TARGET]].replace([np.inf, -np.inf], np.nan)
    training_df = training_df.dropna(subset=[TARGET])

    X = training_df[FEATURES]
    y = training_df[TARGET].astype(int)

    if y.nunique() < 2:
        raise ValueError("Training data must contain both surge and non-surge examples.")

    # 2. Train/Test Split (80% training, 20% testing)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    logger.info("🧠 Training neural network classifier...")
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        (
            "classifier",
            MLPClassifier(
                hidden_layer_sizes=HIDDEN_LAYER_SIZES,
                activation=ACTIVATION,
                solver=SOLVER,
                alpha=ALPHA,
                batch_size=BATCH_SIZE,
                learning_rate_init=LEARNING_RATE_INIT,
                max_iter=EPOCHS,
                early_stopping=EARLY_STOPPING,
                validation_fraction=VALIDATION_FRACTION,
                n_iter_no_change=N_ITER_NO_CHANGE,
                random_state=MODEL_RANDOM_STATE,
            ),
        ),
    ])

    model.fit(X_train, y_train)

    # 3. Evaluate the Model
    logger.info("\n📊 Model Evaluation:")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_prob)

    logger.info(f"Accuracy: {accuracy:.4f} (expected >= {EXPECTED_ACCURACY:.4f})")
    logger.info(f"ROC-AUC Score: {roc_auc:.4f} (expected >= {EXPECTED_ROC_AUC:.4f})")
    logger.info(f"Accuracy Target Met: {'Yes' if accuracy >= EXPECTED_ACCURACY else 'No'}")
    logger.info(f"ROC-AUC Target Met: {'Yes' if roc_auc >= EXPECTED_ROC_AUC else 'No'}")
    logger.info("\nClassification Report:\n", classification_report(y_test, y_pred, zero_division=0))

    # 4. Save the Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    remove_existing_model()
    joblib.dump(model, MODEL_PATH)
    logger.info(f"✅ Neural network model saved successfully to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()