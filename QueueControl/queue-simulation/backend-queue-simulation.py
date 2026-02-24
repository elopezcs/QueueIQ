import pandas as pd
import time
import random
import os
from datetime import datetime, timedelta

# --- CONFIGURATION ---
CSV_FILE = "clinic_queue.csv"
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"] # Our 3 locations
NUM_DOCTORS_PER_CLINIC = 2
SIM_SPEED = 2  # Seconds between "ticks"
TEST_HOUR_OVERRIDE = None 

def init_csv():
    if not os.path.exists(CSV_FILE):
        # Added clinic_id to the schema
        df = pd.DataFrame(columns=["clinic_id", "id", "arrival_time", "acuity", "est_duration"])
        df.to_csv(CSV_FILE, index=False)
        print("Created new multi-clinic clinic_queue.csv")

def get_duration(acuity):
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]

def get_arrival_probability(current_hour):
    if 8 <= current_hour < 11: return 0.60    # Morning Rush
    elif 11 <= current_hour < 14: return 0.15 # Lunch quiet
    elif 16 <= current_hour < 19: return 0.70 # Evening Rush
    else: return 0.25                         # Normal Volume

def get_time_label(hour):
    if 8 <= hour < 11: return "Morning Rush"
    if 11 <= hour < 14: return "Lunch quiet"
    if 16 <= hour < 19: return "Evening Rush"
    return "Normal Volume"

def run_simulation():
    init_csv()
    
    # State: Dictionary tracking free times for doctors AT EACH CLINIC
    doctors_free_at = {cid: [datetime.now()] * NUM_DOCTORS_PER_CLINIC for cid in CLINIC_IDS}
    
    print(f"--- 🏥 MULTI-CLINIC SIMULATION STARTED ---")
    print(f"Tracking {len(CLINIC_IDS)} clinics with {NUM_DOCTORS_PER_CLINIC} doctors each.")
    
    while True:
        try:
            # 1. READ QUEUE
            try:
                df = pd.read_csv(CSV_FILE)
            except pd.errors.EmptyDataError:
                df = pd.DataFrame(columns=["clinic_id", "id", "arrival_time", "acuity", "est_duration"])
            except PermissionError:
                time.sleep(0.1)
                continue

            updated = False
            now = datetime.now()
            current_hour = TEST_HOUR_OVERRIDE if TEST_HOUR_OVERRIDE is not None else now.hour

            # 2. DOCTORS PICK PATIENTS (Grouped by Clinic)
            if not df.empty:
                df = df.sort_values(by=["acuity", "arrival_time"])
                unprocessed_patients = []
                
                for cid in CLINIC_IDS:
                    # Isolate this specific clinic's waiting room
                    clinic_patients = df[df['clinic_id'] == cid].copy()
                    
                    for i in range(NUM_DOCTORS_PER_CLINIC):
                        if now >= doctors_free_at[cid][i] and not clinic_patients.empty:
                            patient = clinic_patients.iloc[0] 
                            duration_min = int(patient['est_duration'])
                            doctors_free_at[cid][i] = now + timedelta(seconds=duration_min) 
                            
                            print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['id']} (Free in {duration_min}s)")
                            
                            clinic_patients = clinic_patients.iloc[1:] 
                            updated = True
                    
                    # Save the remaining waiting patients for this clinic
                    if not clinic_patients.empty:
                        unprocessed_patients.append(clinic_patients)
                
                # Rebuild the dataframe with only the people still waiting
                if unprocessed_patients:
                    df = pd.concat(unprocessed_patients, ignore_index=True)
                else:
                    df = pd.DataFrame(columns=["clinic_id", "id", "arrival_time", "acuity", "est_duration"])

            # 3. DYNAMIC ARRIVALS (Walk-ins for each clinic)
            current_prob = get_arrival_probability(current_hour)
            time_label = get_time_label(current_hour)
            
            for cid in CLINIC_IDS:
                if random.random() < current_prob: 
                    new_id = random.randint(1000, 9999)
                    acuity = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
                    
                    new_p = {
                        "clinic_id": cid,
                        "id": new_id,
                        "arrival_time": now.strftime("%H:%M:%S"),
                        "acuity": acuity,
                        "est_duration": get_duration(acuity)
                    }
                    new_row_df = pd.DataFrame([new_p])
                    df = pd.concat([df, new_row_df], ignore_index=True)
                    
                    print(f"🔔 Walk-in [{time_label}] at {cid}: Patient {new_id} added.")
                    updated = True

            # 4. WRITE UPDATES
            if updated:
                df.to_csv(CSV_FILE, index=False)

            time.sleep(SIM_SPEED)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    run_simulation()