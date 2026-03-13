import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import xgboost as xgb
import joblib

DATA_PATH = "data/synthetic_data/clinic_historical_data.csv"
MODEL_PATH = "models/queueiq_xgb_model.joblib"

def train_model():
    print("📥 Loading synthetic data...")
    df = pd.read_csv(DATA_PATH)
    
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
    import os
    os.makedirs("models", exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"✅ Model saved successfully to {MODEL_PATH}")

if __name__ == "__main__":
    train_model()