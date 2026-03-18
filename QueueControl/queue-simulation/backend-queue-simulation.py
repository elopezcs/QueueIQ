import pandas as pd
import time
import random
import os
from datetime import datetime, timedelta
import joblib
import numpy as np
import psycopg2

# -----------------------------
# DATABASE CONNECTION (Neon)
# -----------------------------
DATABASE_URL = "postgresql://neondb_owner:npg_ew9lIT7oOJMh@ep-super-bar-a8wl4ci7-pooler.eastus2.azure.neon.tech/neondb" 

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS clinic_queue (
            record_id SERIAL PRIMARY KEY,
            clinic_id VARCHAR(100) NOT NULL,
            patient_id INTEGER NOT NULL,
            arrival_time TIMESTAMP NOT NULL,
            acuity INTEGER NOT NULL,
            est_duration INTEGER NOT NULL,
            seen_doctor BOOLEAN DEFAULT FALSE,
            actual_wait_minutes DOUBLE PRECISION
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

# -----------------------------
# Database helper functions
# -----------------------------

def insert_patient(clinic_id, patient_id, arrival_time, acuity, est_duration):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO clinic_queue
        (clinic_id, patient_id, arrival_time, acuity, est_duration, seen_doctor)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (clinic_id, patient_id, arrival_time, acuity, est_duration, False))

    conn.commit()
    cur.close()
    conn.close()
    
# Read queue data from Neon
def fetch_queue():

    conn = get_connection()

    query = """
    SELECT *
    FROM clinic_queue
    ORDER BY clinic_id, seen_doctor, acuity, arrival_time
    """

    df = pd.read_sql_query(query, conn)

    conn.close()

    return df

# Update patient after doctor sees them
def mark_patient_seen(record_id, actual_wait_minutes):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE clinic_queue
        SET seen_doctor = TRUE,
        actual_wait_minutes = %s
        WHERE record_id = %s
    """, (actual_wait_minutes, record_id))

    conn.commit()
    cur.close()
    conn.close()
    
# Load the model once when the application starts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "queueiq_xgb_model.joblib")
)

print("SCRIPT_DIR:", SCRIPT_DIR)
print("MODEL_PATH:", MODEL_PATH)
print("MODEL EXISTS:", os.path.exists(MODEL_PATH))

xgb_model = joblib.load(MODEL_PATH)

# --- CONFIGURATION ---
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"] # Our 3 locations
NUM_DOCTORS_PER_CLINIC = 2
SIM_SPEED = 2  # Seconds between "ticks"

def get_duration(acuity):
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]

# def get_arrival_probability(current_hour):
#     if 8 <= current_hour < 11: return 0.60    # Morning Rush
#     elif 11 <= current_hour < 14: return 0.15 # Lunch quiet
#     elif 16 <= current_hour < 19: return 0.70 # Evening Rush
#     else: return 0.25                         # Normal Volume

def get_surge_probability(current_time: datetime, current_queue_length: int, arrivals_last_1h: int, avg_wait_last_1h: float) -> float:
    """
    Predicts the probability of a patient surge in the next 2 hours.
    """
    # 1. Extract raw time components
    hour_of_day = current_time.hour
    day_of_week = current_time.weekday()
    is_weekend = int(day_of_week >= 5)
    
    # 2. Apply cyclical transformations (must match training exactly)
    hour_sin = np.sin(2 * np.pi * hour_of_day / 24.0)
    hour_cos = np.cos(2 * np.pi * hour_of_day / 24.0)
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    
    # 3. Format features into a DataFrame with the exact column names used in training
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
    
    # 4. Predict probability
    # predict_proba returns an array like [[prob_class_0, prob_class_1]]
    probability = xgb_model.predict_proba(features)[0][1]
    return round(float(probability), 4)

def get_time_label(hour):
    if 8 <= hour < 11: return "Morning Rush"
    if 11 <= hour < 14: return "Lunch quiet"
    if 16 <= hour < 19: return "Evening Rush"
    return "Normal Volume"

def run_simulation():
    init_db()
    
    # State: Tracking free times for doctors
    doctors_free_at = {cid: [datetime.now()] * NUM_DOCTORS_PER_CLINIC for cid in CLINIC_IDS}
    
    print(f"--- 🏥 MULTI-CLINIC SIMULATION STARTED ---")
    print(f"Tracking {len(CLINIC_IDS)} clinics with {NUM_DOCTORS_PER_CLINIC} doctors each.")
    
    while True:
        try:
            # 1. READ QUEUE FROM POSTGRESQL
            df = fetch_queue()

            if not df.empty:
                df['seen_doctor'] = df['seen_doctor'].fillna(False).astype(bool)
                df['actual_wait_minutes'] = pd.to_numeric(df['actual_wait_minutes'], errors='coerce')
                df['arrival_dt'] = pd.to_datetime(df['arrival_time'])

            updated = False
            now = datetime.now()

            if not df.empty:
                # Create a temporary datetime column for easy time math
                df['arrival_dt'] = pd.to_datetime(df['arrival_time'])

                # 2. DOCTORS PICK PATIENTS
                for cid in CLINIC_IDS:
                    # Filter for patients at this clinic who have NOT seen a doctor yet
                    waiting_mask = (df['clinic_id'] == cid) & (~df['seen_doctor'])
                    waiting_patients = df[waiting_mask].sort_values(by=["acuity", "arrival_time"])
                    
                    for i in range(NUM_DOCTORS_PER_CLINIC):
                        if now >= doctors_free_at[cid][i] and not waiting_patients.empty:
                            patient = waiting_patients.iloc[0] 
                            duration_min = int(patient['est_duration'])
                            
                            doctors_free_at[cid][i] = now + timedelta(seconds=duration_min) 
                            
                            wait_min = (now - patient['arrival_dt']).total_seconds() / 60
                            
                            # --- UPDATE DATAFRAME IN-PLACE ---
                        mark_patient_seen(
                                record_id=int(patient['record_id']),
                                actual_wait_minutes=float(wait_min)
                           )

                        print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['patient_id']} (Waited: {wait_min:.1f}m, Free in {duration_min}s)")
                            
                        waiting_patients = waiting_patients.iloc[1:] 
                        updated = True

            # 3. DYNAMIC ARRIVALS (Walk-ins for each clinic)
            # current_prob = get_arrival_probability(current_hour)
            # time_label = get_time_label(current_hour)

            # Get the current local time dynamically
            now = datetime.now() 
            
            # NOTE: In a live production environment, these variables would be 
            # calculated dynamically by querying your active QueueIQ database. 
            # We are keeping them hardcoded here just to test the function.
            queue_len = 5
            recent_arrivals = 8
            recent_wait = 25.5
            
            current_prob = get_surge_probability(now, queue_len, recent_arrivals, recent_wait)
            
            for cid in CLINIC_IDS:
                if df.empty:
                    queue_len = 0
                    recent_arrivals = 0
                    recent_wait = 0.0
                else:
                    clinic_df = df[df['clinic_id'] == cid]
                    
                    queue_len = len(clinic_df[~clinic_df['seen_doctor']])
                    
                    # Ensure 'arrival_dt' exists before filtering
                    if 'arrival_dt' in clinic_df.columns:
                        one_hour_ago = now - timedelta(seconds=60)
                        recent_patients = clinic_df[clinic_df['arrival_dt'] >= one_hour_ago]
                        recent_arrivals = len(recent_patients)
                        
                        completed_recent = recent_patients[recent_patients['seen_doctor'] == True]
                        recent_wait = completed_recent['actual_wait_minutes'].mean() if not completed_recent.empty else 0.0
                    else:
                        recent_arrivals = 0
                        recent_wait = 0.0
                    
                    if pd.isna(recent_wait): 
                        recent_wait = 0.0
                
                # Get the probability of a surge from the model
                surge_prob = get_surge_probability(now, queue_len, recent_arrivals, recent_wait)
                
                # MAP SURGE TO ARRIVAL RATE: 
                # Base trickle rate is 5% per tick. If surge_prob is 100%, it scales up to a 60% chance per tick.
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
                    
                    print(f"🔔 Walk-in [{now.strftime('%Y-%m-%d %H:%M:%S')}] at clinic {cid}: Patient {new_id} added with dynamic Surge Probability of {current_prob * 100:.1f}%")
                    updated = True

            # 4. WRITE UPDATES
            time.sleep(SIM_SPEED)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_simulation()