import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime

# --- CONFIGURATION ---
CSV_FILE = "clinic_queue.csv"
CLINIC_CHOICES = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]

st.set_page_config(layout="wide", page_title="Multi-Clinic Dashboard")

# --- HELPER FUNCTIONS ---
def load_data():
    try:
        df = pd.read_csv(CSV_FILE)
        # Ensure seen_doctor is treated as a boolean for reliable filtering
        if 'seen_doctor' in df.columns:
            df['seen_doctor'] = df['seen_doctor'].astype(bool)
        return df
    except Exception as e:
        # Updated fallback schema to match the new backend
        return pd.DataFrame(columns=[
            "clinic_id", "id", "arrival_time", "acuity", 
            "est_duration", "seen_doctor", "actual_wait_minutes"
        ])

def add_patient_to_csv(target_clinic, acuity=None):
    df = load_data()
    
    new_id = random.randint(1000, 9999)
    if not acuity:
        acuity = random.choice([3, 4, 5])
    
    new_p = {
        "clinic_id": target_clinic,
        "id": new_id,
        "arrival_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Updated to match backend datetime format
        "acuity": acuity,
        "est_duration": {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity],
        "seen_doctor": False,       # New patient hasn't seen a doctor yet
        "actual_wait_minutes": None # Wait time is unknown upon arrival
    }
    
    new_row_df = pd.DataFrame([new_p])
    df = pd.concat([df, new_row_df], ignore_index=True)
    
    df.to_csv(CSV_FILE, index=False)
    st.toast(f"✅ Patient {new_id} added to {target_clinic}!")

# --- UI LAYOUT ---
st.title("🏥 QueueIQ (CareFlow) Live Dashboard")

# Load full dataset
full_df = load_data()

# Clinic Selector (Dropdown)
selected_clinic = st.selectbox("📍 Select Clinic to View/Manage:", CLINIC_CHOICES)

# Filter data for the selected clinic AND only show patients who are STILL WAITING
if not full_df.empty and 'clinic_id' in full_df.columns and 'seen_doctor' in full_df.columns:
    # The tilde (~) means "NOT", so this grabs rows where seen_doctor is False
    df_waiting = full_df[(full_df['clinic_id'] == selected_clinic) & (~full_df['seen_doctor'])]
    total_waiting_system = len(full_df[~full_df['seen_doctor']])
else:
    # Empty state fallback
    df_waiting = pd.DataFrame(columns=[
        "clinic_id", "id", "arrival_time", "acuity", 
        "est_duration", "seen_doctor", "actual_wait_minutes"
    ])
    total_waiting_system = 0

# 1. METRICS ROW
col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Queue at {selected_clinic}", len(df_waiting))

if not df_waiting.empty:
    # Sort the dataframe locally by acuity and time so the "Next Up" metric matches the backend logic
    df_waiting = df_waiting.sort_values(by=["acuity", "arrival_time"])
    col2.metric("Next Up", df_waiting.iloc[0]['id'])
else:
    col2.metric("Next Up", "None")

col3.metric("Total System Queue (All Clinics)", total_waiting_system)
col4.caption("updates every 2s")

# 2. MAIN CONTENT
c_table, c_actions = st.columns([3, 1])

with c_table:
    st.subheader(f"📋 Current Queue: {selected_clinic}")
    if not df_waiting.empty:
        def highlight_critical(val):
            return 'background-color: #ffcccc' if val == 1 else ''
        
        # Hide the redundant backend columns from the UI table for a cleaner look
        display_cols_to_drop = ['clinic_id', 'seen_doctor', 'actual_wait_minutes']
        display_df = df_waiting.drop(columns=display_cols_to_drop, errors='ignore')
        
        st.dataframe(
            display_df.style.map(highlight_critical, subset=['acuity']), 
            width='stretch',
            hide_index=True
        )
    else:
        st.info(f"The waiting room at {selected_clinic} is empty.")

with c_actions:
    st.subheader("Reception Desk")
    st.write(f"Add patients to **{selected_clinic}**:")
    
    if st.button("➕ Add Standard Patient", key="btn_std"):
        add_patient_to_csv(selected_clinic)
        
    if st.button("🚨 Add Critical (Acuity 1)", key="btn_crit"):
        add_patient_to_csv(selected_clinic, acuity=1)

# --- AUTO-REFRESH LOOP ---
time.sleep(2)
st.rerun()