import os
import time
import random
from datetime import datetime, timedelta
import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import urlparse

# -----------------------------
# DATABASE
# -----------------------------
DATABASE_URL = "postgresql://neondb_owner:npg_shDqYzGe45VH@ep-morning-sound-a8wgaqeq-pooler.eastus2.azure.neon.tech/neondb"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# -----------------------------
# MODEL
# -----------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "queueiq_xgb_model.joblib")
)

print("MODEL_PATH:", MODEL_PATH)
print("MODEL EXISTS:", os.path.exists(MODEL_PATH))

xgb_model = joblib.load(MODEL_PATH)

# -----------------------------
# CONFIG
# -----------------------------
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]
NUM_DOCTORS_PER_CLINIC = 2
SIM_SPEED = 2  # seconds between ticks

# est_duration is stored in seconds in this simulation
def get_duration(acuity: int) -> int:
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]


def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clinic_queue (
                record_id SERIAL PRIMARY KEY,
                clinic_id VARCHAR(100) NOT NULL,
                patient_id INTEGER NOT NULL,
                arrival_time TIMESTAMP NOT NULL,
                acuity INTEGER NOT NULL,
                est_duration INTEGER NOT NULL
            );
        """))


def fetch_queue() -> pd.DataFrame:
    query = text("""
        SELECT record_id, clinic_id, patient_id, arrival_time, acuity, est_duration
        FROM clinic_queue
        ORDER BY clinic_id, acuity ASC, arrival_time ASC
    """)
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn)


def insert_patient(clinic_id: str, patient_id: int, arrival_time: datetime, acuity: int, est_duration: int):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO clinic_queue (clinic_id, patient_id, arrival_time, acuity, est_duration)
            VALUES (:clinic_id, :patient_id, :arrival_time, :acuity, :est_duration)
        """), {
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "arrival_time": arrival_time,
            "acuity": acuity,
            "est_duration": est_duration,
        })


def delete_patient(record_id: int):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM clinic_queue
            WHERE record_id = :record_id
        """), {"record_id": record_id})


def get_surge_probability(
    current_time: datetime,
    current_queue_length: int,
    arrivals_last_1h: int,
    avg_wait_last_1h: float
) -> float:
    hour_of_day = current_time.hour
    day_of_week = current_time.weekday()
    is_weekend = int(day_of_week >= 5)

    hour_sin = np.sin(2 * np.pi * hour_of_day / 24.0)
    hour_cos = np.cos(2 * np.pi * hour_of_day / 24.0)
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)

    features = pd.DataFrame([{
        "is_weekend": is_weekend,
        "day_sin": day_sin,
        "day_cos": day_cos,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "queue_length_at_arrival": current_queue_length,
        "arrivals_last_1_hour": arrivals_last_1h,
        "avg_wait_last_1_hour": avg_wait_last_1h
    }])

    probability = xgb_model.predict_proba(features)[0][1]
    return round(float(probability), 4)


def run_simulation():
    init_db()

    doctors_free_at = {
        cid: [datetime.now()] * NUM_DOCTORS_PER_CLINIC
        for cid in CLINIC_IDS
    }

    print("--- 🏥 MULTI-CLINIC SIMULATION STARTED ---")
    print(f"Tracking {len(CLINIC_IDS)} clinics with {NUM_DOCTORS_PER_CLINIC} doctors each.")

    while True:
        try:
            df = fetch_queue()
            now = datetime.now()

            if not df.empty:
                df["arrival_time"] = pd.to_datetime(df["arrival_time"])

                # 1) Doctors take next patient and REMOVE that row from DB
                for cid in CLINIC_IDS:
                    waiting_patients = df[df["clinic_id"] == cid].sort_values(
                        by=["acuity", "arrival_time"]
                    )

                    for i in range(NUM_DOCTORS_PER_CLINIC):
                        if now >= doctors_free_at[cid][i] and not waiting_patients.empty:
                            patient = waiting_patients.iloc[0]
                            duration_sec = int(patient["est_duration"])

                            doctors_free_at[cid][i] = now + timedelta(seconds=duration_sec)

                            print(f"🗑️ Deleting record_id: {patient['record_id']}")
                            delete_patient(int(patient["record_id"]))

                            waited_min = (now - patient["arrival_time"]).total_seconds() / 60.0
                            print(
                                f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['patient_id']} "
                                f"(waited {waited_min:.1f} min, busy for {duration_sec}s)"
                            )

                            waiting_patients = waiting_patients.iloc[1:]

            # refresh queue after deletions
            df = fetch_queue()
            now = datetime.now()

            if not df.empty:
                df["arrival_time"] = pd.to_datetime(df["arrival_time"])

            # 2) Dynamic arrivals
            for cid in CLINIC_IDS:
                clinic_df = df[df["clinic_id"] == cid] if not df.empty else pd.DataFrame()

                queue_len = len(clinic_df)

                if not clinic_df.empty:
                    one_hour_ago = now - timedelta(hours=1)
                    recent_patients = clinic_df[clinic_df["arrival_time"] >= one_hour_ago]
                    recent_arrivals = len(recent_patients)

                    # average current waiting time among patients that arrived within last hour
                    if not recent_patients.empty:
                        recent_wait = (
                            (now - recent_patients["arrival_time"])
                            .dt.total_seconds()
                            .mean() / 60.0
                        )
                    else:
                        recent_wait = 0.0
                else:
                    recent_arrivals = 0
                    recent_wait = 0.0

                surge_prob = get_surge_probability(now, queue_len, recent_arrivals, recent_wait)
                current_prob = 0.05 + (surge_prob * 0.55)

                if random.random() < current_prob:
                    new_id = random.randint(1000, 9999)
                    acuity = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]

                    insert_patient(
                        clinic_id=cid,
                        patient_id=new_id,
                        arrival_time=now,
                        acuity=acuity,
                        est_duration=get_duration(acuity)
                    )

                    print(
                        f"🔔 Walk-in [{now.strftime('%Y-%m-%d %H:%M:%S')}] "
                        f"{cid}: Patient {new_id} added "
                        f"(surge {current_prob * 100:.1f}%)"
                    )

            time.sleep(SIM_SPEED)

        except KeyboardInterrupt:
            print("\n🛑 Simulation stopped by user.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    run_simulation()