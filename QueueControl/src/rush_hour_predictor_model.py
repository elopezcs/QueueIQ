import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import xgboost as xgb
import joblib
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# -----------------------------
# DATABASE & ENVIRONMENT
# -----------------------------
_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path=_ENV_PATH, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in .env. Please set it before running.")
    exit(1)
    
try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except Exception as e:
    print(f"❌ Failed to connect to the database: {e}")
    exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TABLE_NAME = "clinic_historical_data"
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_model.joblib")
)


def load_training_data() -> pd.DataFrame:
    query = text(f"SELECT * FROM {TABLE_NAME}")
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)

    if df.empty:
        raise ValueError(
            f"Table '{TABLE_NAME}' is empty. Generate or load synthetic data before training the model."
        )

    return df


def remove_existing_model():
    if os.path.exists(MODEL_PATH):
        os.remove(MODEL_PATH)
        print(f"🗑️ Deleted existing model at {MODEL_PATH}")

def train_model():
    print(f"📥 Loading training data from database table '{TABLE_NAME}'...")
    df = load_training_data()
    
    # 1. Define Features (X) and Target (y)
    # We drop identifiers and future-leaking columns (like arrivals_next_2_hours)
    features = [
        "is_weekend", "day_sin", "day_cos", 
        "hour_sin", "hour_cos", 
        "queue_length_at_arrival", "arrivals_last_1_hour", "avg_wait_last_1_hour"
    ]
    
    X = df[features]
    y = df['is_surge_imminent']
    
    # 2. Train/Test Split (80% training, 20% testing)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print("🧠 Training XGBoost Classifier...")
    # Initialize the model. Using logloss for probability outputs.
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective='binary:logistic',
        eval_metric='logloss',
        use_label_encoder=False
    )
    
    model.fit(X_train, y_train)
    
    # 3. Evaluate the Model
    print("\n📊 Model Evaluation:")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1] # Get probability of class 1 (Surge)
    
    print(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))
    
    # 4. Save the Model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    remove_existing_model()
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved successfully to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()