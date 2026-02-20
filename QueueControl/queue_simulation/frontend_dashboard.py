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
        return pd.read_csv(CSV_FILE)
    except:
        # Include clinic_id in the fallback schema
        return pd.DataFrame(columns=["clinic_id", "id", "arrival_time", "acuity", "est_duration"])

def add_patient_to_csv(target_clinic, acuity=None):
    df = load_data()
    
    new_id = random.randint(1000, 9999)
    if not acuity:
        acuity = random.choice([3, 4, 5])
    
    new_p = {
        "clinic_id": target_clinic,
        "id": new_id,
        "arrival_time": datetime.now().strftime("%H:%M:%S"),
        "acuity": acuity,
        "est_duration": {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]
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

# Filter data for the selected clinic
if not full_df.empty and 'clinic_id' in full_df.columns:
    df = full_df[full_df['clinic_id'] == selected_clinic]
else:
    df = pd.DataFrame(columns=["clinic_id", "id", "arrival_time", "acuity", "est_duration"])

# 1. METRICS ROW
col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Queue at {selected_clinic}", len(df))

if not df.empty:
    col2.metric("Next Up ", df.iloc[0]['id'])
else:
    col2.metric("Next Up", "None")

col3.metric("Total System Queue (All Clinics)", len(full_df))
col4.caption("updates every 2s")

# 2. MAIN CONTENT
c_table, c_actions = st.columns([3, 1])

with c_table:
    st.subheader(f"📋 Current Queue: {selected_clinic}")
    if not df.empty:
        def highlight_critical(val):
            return 'background-color: #ffcccc' if val == 1 else ''
        
        # Hide the clinic_id column from the UI since it's redundant here
        display_df = df.drop(columns=['clinic_id'], errors='ignore')
        
        st.dataframe(
            display_df.style.map(highlight_critical, subset=['acuity']), 
            use_container_width=True,
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