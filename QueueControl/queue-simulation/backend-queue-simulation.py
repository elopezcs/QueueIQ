import pandas as pd
import time
import random
import os
from datetime import datetime, timedelta
import joblib
import numpy as np

# Load the model once when the application starts
MODEL_PATH = "models/queueiq_xgb_model.joblib"
xgb_model = joblib.load(MODEL_PATH)

# --- CONFIGURATION ---
CSV_FILE = "clinic_queue.csv"
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"] # Our 3 locations
NUM_DOCTORS_PER_CLINIC = 2
SIM_SPEED = 2  # Seconds between "ticks"

def init_csv():
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=[
            "clinic_id", "id", "arrival_time", "acuity", 
            "est_duration", "seen_doctor", "actual_wait_minutes"
        ])
        df.to_csv(CSV_FILE, index=False)
        print("Created new multi-clinic clinic_queue.csv")

def get_duration(acuity):
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]

def get_surge_probability(current_time: datetime, current_queue_length: int, arrivals_last_1h: int, avg_wait_last_1h: float) -> float:
    """Predicts the probability of a patient surge in the next 2 hours."""
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
    init_csv()
    
    # State: Tracking free times for doctors
    doctors_free_at = {cid: [datetime.now()] * NUM_DOCTORS_PER_CLINIC for cid in CLINIC_IDS}
    
    print(f"--- 🏥 MULTI-CLINIC SIMULATION STARTED ---")
    print(f"Tracking {len(CLINIC_IDS)} clinics with {NUM_DOCTORS_PER_CLINIC} doctors each.")
    
    while True:
        try:
            # 1. READ QUEUE
            try:
                df = pd.read_csv(CSV_FILE)
            except pd.errors.EmptyDataError:
                df = pd.DataFrame(columns=[
                    "clinic_id", "id", "arrival_time", "acuity", 
                    "est_duration", "seen_doctor", "actual_wait_minutes"
                ])
            except PermissionError:
                time.sleep(0.1)
                continue

            # Ensure data types are correct when reading from CSV
            if not df.empty:
                # Safely parse strings to actual booleans to avoid "False" evaluating to True
                if df['seen_doctor'].dtype == object:
                    df['seen_doctor'] = df['seen_doctor'].map(
                        {'True': True, 'False': False, 'true': True, 'false': False, True: True, False: False}
                    ).fillna(False).astype(bool)
                else:
                    df['seen_doctor'] = df['seen_doctor'].astype(bool)
                    
                df['actual_wait_minutes'] = pd.to_numeric(df['actual_wait_minutes'], errors='coerce')

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
                            
                            wait_min = (now - patient['arrival_dt']).total_seconds()
                            
                            # --- UPDATE DATAFRAME IN-PLACE ---
                            idx = patient.name 
                            df.at[idx, 'seen_doctor'] = True
                            df.at[idx, 'actual_wait_minutes'] = wait_min
                            
                            print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['id']} (Waited: {wait_min:.1f}m, Free in {duration_min}s)")
                            
                            waiting_patients = waiting_patients.iloc[1:] 
                            updated = True

            # 3. DYNAMIC ARRIVALS (Walk-ins for each clinic)
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
                    
                    new_p = {
                        "clinic_id": cid,
                        "id": new_id,
                        "arrival_time": now.strftime("%Y-%m-%d %H:%M:%S"), 
                        "acuity": acuity,
                        "est_duration": get_duration(acuity),
                        "seen_doctor": False,
                        "actual_wait_minutes": None
                    }
                    
                    new_row_df = pd.DataFrame([new_p])
                    df = pd.concat([df, new_row_df], ignore_index=True)
                    
                    print(f"🔔 Walk-in [{now.strftime('%H:%M:%S')}] at {cid}: Patient {new_id} | Q: {queue_len}, Surge Prob: {surge_prob * 100:.1f}% -> Spawn Chance: {current_prob * 100:.1f}%")
                    updated = True

            # 4. WRITE UPDATES
            if updated:
                # Drop the temporary datetime object column before saving back to CSV
                if 'arrival_dt' in df.columns:
                    df = df.drop(columns=['arrival_dt'])
                df.to_csv(CSV_FILE, index=False)

            time.sleep(SIM_SPEED)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_simulation()