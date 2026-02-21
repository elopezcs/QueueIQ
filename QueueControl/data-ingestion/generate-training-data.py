import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- CONFIGURATION ---
OUTPUT_FILE = "clinic_historical_data.csv"
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]
NUM_DOCTORS = 2
DAYS_TO_SIMULATE = 180  # 6 months of data
START_DATE = datetime(2023, 1, 1, 8, 0, 0)

def get_duration(acuity):
    """Adds realistic variation to doctor service times."""
    base = {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]
    noise = np.random.normal(0, 3) # +/- 3 minutes of random variation
    return max(1, int(base + noise))

def generate_data():
    print(f"⚙️ Generating {DAYS_TO_SIMULATE} days of synthetic history...")
    all_visits = []

    # 1. GENERATE ARRIVALS (With realistic Rush Hours)
    for day in range(DAYS_TO_SIMULATE):
        current_date = START_DATE + timedelta(days=day)
        is_weekend = current_date.weekday() >= 5
        
        for clinic in CLINIC_IDS:
            for hour in range(8, 20): # Clinics open 8 AM to 8 PM
                # Define baseline arrival rates
                if 8 <= hour < 11: 
                    rate = 8  # Morning Rush
                elif 11 <= hour < 14: 
                    rate = 3  # Lunch Lull
                elif 16 <= hour < 19: 
                    rate = 10 # Evening Rush
                else: 
                    rate = 4  # Normal
                
                # Weekends are slightly busier
                if is_weekend: rate = int(rate * 1.2)
                
                # Use Poisson distribution for realistic bunching of arrivals
                num_arrivals = np.random.poisson(rate)
                
                for _ in range(num_arrivals):
                    minute = np.random.randint(0, 60)
                    arrival_time = current_date.replace(hour=hour, minute=minute)
                    acuity = np.random.choice([1, 2, 3, 4, 5], p=[0.05, 0.10, 0.50, 0.25, 0.10])
                    
                    all_visits.append({
                        "clinic_id": clinic,
                        "arrival_time": arrival_time,
                        "day_of_week": current_date.weekday(), # 0=Mon, 6=Sun
                        "is_weekend": int(is_weekend),
                        "hour_of_day": hour,
                        "acuity": acuity,
                        "est_duration": get_duration(acuity)
                    })

    # Sort all arrivals chronologically
    df_visits = pd.DataFrame(all_visits)
    df_visits = df_visits.sort_values(by=["clinic_id", "arrival_time"]).reset_index(drop=True)

    print(f"📊 Processing queue dynamics for {len(df_visits)} visits...")

    # 2. SIMULATE THE QUEUE (To calculate ground truth targets)
    final_data = []
    
    for clinic in CLINIC_IDS:
        clinic_data = df_visits[df_visits['clinic_id'] == clinic].to_dict('records')
        
        doctors_free_at = [START_DATE] * NUM_DOCTORS
        queue_history = [] # Stores (arrival_time, service_start_time)
        
        for v in clinic_data:
            arr = v['arrival_time']
            
            # --- CALCULATE FEATURE: Queue Length ---
            # How many previous patients are still waiting when this patient walks in?
            q_len = sum(1 for h_arr, h_start in queue_history if h_arr <= arr and h_start > arr)
            v['queue_length_at_arrival'] = q_len
            
            # --- CALCULATE TARGET 1: Actual Wait Time ---
            doctors_free_at.sort()
            earliest_free = doctors_free_at[0]
            
            if earliest_free <= arr:
                start_time = arr
                wait_min = 0
            else:
                start_time = earliest_free
                wait_min = (start_time - arr).total_seconds() / 60.0
                
            # Update doctor schedule
            doctors_free_at[0] = start_time + timedelta(minutes=v['est_duration'])
            queue_history.append((arr, start_time))
            
            v['actual_wait_minutes'] = round(wait_min, 1)
            final_data.append(v)

    df_final = pd.DataFrame(final_data)

    # --- CALCULATE TARGET 2: Rush Hour Probability ---
    # For every visit, count how many total patients arrive in the next 2 hours
    print("⏳ Calculating surge prediction targets...")
    df_final = df_final.sort_values(by=["clinic_id", "arrival_time"]).reset_index(drop=True)
    
    # We use a rolling window to look ahead 2 hours
    df_final = df_final.set_index('arrival_time')
    
    arrivals_next_2h = []
    for clinic in CLINIC_IDS:
        c_df = df_final[df_final['clinic_id'] == clinic]
        # Count rows in a 2-hour rolling window, shifted backwards to look into the future
        future_counts = c_df['clinic_id'].rolling('2H').count().shift(-1).fillna(0)
        arrivals_next_2h.extend(future_counts.tolist())

    df_final = df_final.reset_index()
    df_final['arrivals_next_2_hours'] = arrivals_next_2h
    
    # Define a "Rush Hour Surge" as > 15 arrivals in the next 2 hours (Binary Classification Target)
    df_final['is_surge_imminent'] = (df_final['arrivals_next_2_hours'] > 15).astype(int)

    # 3. EXPORT
    cols_order = [
        "clinic_id", "arrival_time", "day_of_week", "is_weekend", "hour_of_day", 
        "acuity", "est_duration", "queue_length_at_arrival", 
        "actual_wait_minutes", "arrivals_next_2_hours", "is_surge_imminent"
    ]
    df_final = df_final[cols_order]
    
    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Success! Saved {len(df_final)} rows to {OUTPUT_FILE}")
    print("\nSample Data:")
    print(df_final[['arrival_time', 'hour_of_day', 'queue_length_at_arrival', 'actual_wait_minutes', 'is_surge_imminent']].head())

if __name__ == "__main__":
    generate_data()