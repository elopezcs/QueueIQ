import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
from sklearn.impute import SimpleImputer
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from database.database_manager import DatabaseManager

# -----------------------------
# DATABASE & ENVIRONMENT
# -----------------------------

try:
    db_manager = DatabaseManager()
    db_manager.init_db()
except Exception as e:
    print(f"**❌ Failed to connect to the database:** {e}")
    exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_NAME = "clinic_historical_data"
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_model.joblib")
)


def remove_existing_model():
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        print(f"🗑️ Deleted existing model at {MODEL_PATH}")


def train_model():
    print(f"📥 Loading training data from database table '{TABLE_NAME}'...")
    df = db_manager.fetch_training_data(TABLE_NAME)

    # 1. Define Features (X) and Target (y)
    # We drop identifiers and future-leaking columns (like arrivals_next_2_hours)
    features = [
        "is_weekend", "day_sin", "day_cos",
        "hour_sin", "hour_cos",
        "queue_length_at_arrival", "arrivals_last_1_hour", "avg_wait_last_1_hour"
    ]

    training_df = df[features + ["is_surge_imminent"]].replace([np.inf, -np.inf], np.nan)
    training_df = training_df.dropna(subset=["is_surge_imminent"])

    X = training_df[features]
    y = training_df["is_surge_imminent"].astype(int)

    if y.nunique() < 2:
        raise ValueError("Training data must contain both surge and non-surge examples.")

    # 2. Train/Test Split (80% training, 20% testing)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("🧠 Training neural network classifier...")
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
    print("\n📊 Model Evaluation:")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred, zero_division=0))

    # 4. Save the Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    remove_existing_model()
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Neural network model saved successfully to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()