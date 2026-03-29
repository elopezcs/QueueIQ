import os
import sys
import time
import random
import threading
import importlib.util
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

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
    st.error(f"**❌ Failed to connect to the database:** {e}")
    st.stop()

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide", page_title="Multi-Clinic Dashboard")

# -----------------------------
# SHARED STATE (UI <-> THREAD)
# -----------------------------
CLINIC_IDS = db_manager.fetch_clinics()['clinic_id'].tolist()  # Fetch clinic IDs from the database

# @st.cache_resource keeps these dictionaries alive across Streamlit reruns
# and makes them accessible to the background thread.
@st.cache_resource
def get_sim_config():
    return {"num_doctors": 1, "sim_speed": 2.0}

@st.cache_resource
def get_doctors_state():
    return {cid: [datetime.now()] for cid in CLINIC_IDS}

sim_config = get_sim_config()
doctors_free_at = get_doctors_state()

# -----------------------------
# MODEL
# -----------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "rush_hour_predictor_model.joblib")
)
TRAINING_SCRIPT_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "src", "rush_hour_predictor_model.py")
)

try:
    rush_hour_predictor_model = joblib.load(MODEL_PATH)
except FileNotFoundError:
    st.error(f"**❌ Rush Hour Predictor model not found at {MODEL_PATH}.** Please ensure the model exists.")
    st.stop()


def retrain_rush_hour_model():
    global rush_hour_predictor_model

    spec = importlib.util.spec_from_file_location("rush_hour_predictor_model", TRAINING_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load training script from {TRAINING_SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.train_model()
    rush_hour_predictor_model = joblib.load(MODEL_PATH)

# -----------------------------
# BACKEND HELPERS
# -----------------------------
def get_duration(priority: int) -> int:
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]

def get_surge_probability() -> float:
    
    df = db_manager.fetch_queue()
    now = datetime.now()
    if not df.empty:
        df["arrival_time"] = pd.to_datetime(df["arrival_time"])

    for cid in CLINIC_IDS:
        clinic_df = df[df["clinic_id"] == cid] if not df.empty else pd.DataFrame()
        
        recent_arrivals = 0
        recent_wait = 0.0
        if not clinic_df.empty:
            recent_patients = clinic_df[clinic_df["arrival_time"] >= (now - timedelta(hours=1))]
            recent_arrivals = len(recent_patients)
            if not recent_patients.empty:
                recent_wait = (now - recent_patients["arrival_time"]).dt.total_seconds().mean() / 60.0

    hour_of_day = now.hour
    day_of_week = now.weekday()
    
    features = pd.DataFrame([{
        "is_weekend": int(day_of_week >= 5),
        "day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
        "day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
        "hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
        "hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
        "queue_length_at_arrival": len(clinic_df),
        "arrivals_last_1_hour": recent_arrivals,
        "avg_wait_last_1_hour": recent_wait
    }])

    rush_hour_probability = round(float(rush_hour_predictor_model.predict_proba(features)[0][1]), 4)

    return rush_hour_probability

# -----------------------------
# BACKGROUND SIMULATION THREAD
# -----------------------------
def run_simulation():
    print("--- 🏥 BACKGROUND SIMULATION STARTED ---")

    while True:
        try:
            # 1. Read dynamic config values
            current_doctors = sim_config["num_doctors"]
            current_speed = sim_config["sim_speed"]

            df = db_manager.fetch_queue()
            now = datetime.now()

            if not df.empty:
                df["arrival_time"] = pd.to_datetime(df["arrival_time"])

                for cid in CLINIC_IDS:
                    # Dynamically adjust doctor lists if the UI slider changed
                    while len(doctors_free_at[cid]) < current_doctors:
                        doctors_free_at[cid].append(now)
                    while len(doctors_free_at[cid]) > current_doctors:
                        doctors_free_at[cid].pop()

                    waiting_patients = df[df["clinic_id"] == cid].sort_values(by=["priority", "arrival_time"])

                    for i in range(current_doctors):
                        if now >= doctors_free_at[cid][i] and not waiting_patients.empty:
                            patient = waiting_patients.iloc[0]
                            duration_sec = int(patient["est_duration"])
                            doctors_free_at[cid][i] = now + timedelta(seconds=duration_sec)

                            db_manager.delete_patient(int(patient["record_id"]))
                            waited_min = (now - patient["arrival_time"]).total_seconds() / 60.0
                            print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['patient_id']} (waited {waited_min:.1f} min)")

                            waiting_patients = waiting_patients.iloc[1:]

            # 2. Dynamic arrivals
                surge_prob = get_surge_probability()
                current_prob = 0.05 + (surge_prob * 0.55)

                if random.random() < current_prob:
                    new_id = random.randint(1000, 9999)
                    priority = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
                    db_manager.insert_patient(cid, new_id, now, priority, get_duration(priority))
                    print(f"🔔 Walk-in [{now.strftime('%H:%M:%S')}] {cid}: Patient {new_id} added")

            # Pause based on the dynamic slider speed
            time.sleep(current_speed)

        except Exception as e:
            print(f"Simulation Error: {e}")
            time.sleep(1)

# Start thread only once
if "sim_thread_started" not in st.session_state:
    try:
        db_manager = DatabaseManager()
        db_manager.init_db()
    except Exception as db_err:
        st.error(
            f"**Database connection failed.** Ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct.\n\n"
            f"Error: `{db_err}`"
        )
        st.stop()
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()
    st.session_state.sim_thread_started = True


# -----------------------------
# FRONTEND UI
# -----------------------------
# Sidebar Controls for the Simulation
with st.sidebar:
    try:
        sidebar_queue_df = db_manager.fetch_queue()
        total_waiting_system = len(sidebar_queue_df)
    except Exception:
        total_waiting_system = 0

    st.metric("Total System Queue (All Clinics)", total_waiting_system)

    selected_clinic = st.selectbox(
        "📍 Select Clinic to View/Manage:",
        CLINIC_IDS,
        key="selected_clinic",
    )
    
    st.header(f"Current Rush Hour Surge Probability: {get_surge_probability() * 100:.1f}%")
    
    # Add a button to retrain the model, and it would re-run the training code from rush_hour_predictor_model.py and update the model file.
    if st.button("🔄 Retrain Rush Hour Model", key="btn_retrain_model"):
        with st.spinner("Retraining model... This may take a moment."):
            try:
                retrain_rush_hour_model()
                st.success("✅ Model retrained successfully!")
            except Exception as e:
                st.error(f"❌ Model retraining failed: {e}")

    # st.markdown("---")
    
    sim_config["num_doctors"] = st.slider(
        "Doctors per Clinic", 
        min_value=0, max_value=10, value=sim_config["num_doctors"], step=1,
        help="Change this to dynamically add or remove doctors from the simulation."
    )
    
    sim_config["sim_speed"] = st.slider(
        "Update Speed (seconds/update)", 
        min_value=0.5, max_value=10.0, value=sim_config["sim_speed"], step=0.5,
        help="A value of 2 means the simulation and dashboard refresh once every 2 seconds."
    )

    # st.markdown("---")

    # Add a dropdown to select patient priority and a button to add a new patient with that priority
    # write a word next to each priority level to indicate the urgency (e.g. 1 = Critical, 5 = Low)
    priority_labels = {
        1: "Critical",
        2: "High",
        3: "Medium",
        4: "Low",
        5: "Very Low"
    }
    selected_priority = st.selectbox(
        "Add Patient Priority:",
        options=list(priority_labels.keys()),   
        format_func=lambda x: f"{x} - {priority_labels[x]}",
        index=2
    )
    if st.button("➕ Add Patient to All Clinics", key="btn_add_patient_all"):
        now = datetime.now()
        for cid in CLINIC_IDS:
            new_id = random.randint(1000, 9999)
            db_manager.insert_patient(cid, new_id, now, selected_priority, get_duration(selected_priority))
        st.toast(f"✅ Patient (Priority {selected_priority}) added to all clinics!")

@st.fragment(run_every=timedelta(seconds=float(sim_config["sim_speed"])))
def render_dashboard():
    st.title("🏥 QueueIQ Live Dashboard")

    try:
        full_df = db_manager.fetch_queue()
        if not full_df.empty:
            full_df["arrival_time"] = pd.to_datetime(full_df["arrival_time"])
    except Exception as e:
        st.error(f"Database error: {e}")
        full_df = pd.DataFrame()

    if not full_df.empty and "clinic_id" in full_df.columns:
        df_waiting = full_df[full_df["clinic_id"] == selected_clinic].copy()
    else:
        df_waiting = pd.DataFrame(
            columns=["record_id", "clinic_id", "patient_id", "arrival_time", "priority", "est_duration"]
        )

    col1, col2 = st.columns(2)
    col1.metric(f"Queue at {selected_clinic}", len(df_waiting))

    if not df_waiting.empty:
        df_waiting = df_waiting.sort_values(by=["priority", "arrival_time"])
        col2.metric("Next Up", int(df_waiting.iloc[0]["patient_id"]))
    else:
        col2.metric("Next Up", "None")

    c_table, c_actions = st.columns([3, 1])

    with c_table:
        st.subheader(f"📋 Current Queue: {selected_clinic}")

        if not df_waiting.empty:
            display_df = df_waiting.copy()
            display_df["arrival_time"] = display_df["arrival_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
            display_df = display_df.drop(columns=["record_id", "clinic_id"], errors="ignore")

            st.dataframe(
                display_df.style.map(
                    lambda v: "background-color: #ffcccc" if v == 1 else "",
                    subset=["priority"],
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info(f"The waiting room at {selected_clinic} is empty.")

    with c_actions:

        surge_prob = get_surge_probability()
        
        # Add a gauge chart to show the surge probability, with green for low, yellow for medium, and red for high probabilities.
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = surge_prob * 100,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Rush Hour Probability"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "black"},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgreen"},
                        {'range': [50, 80], 'color': "yellow"},
                        {'range': [80, 100], 'color': "red"}]
                }
        ))

        st.plotly_chart(fig)

    # Draw a moving average line chart of the number of patients in the queue over time for the selected clinic, with a line for each priority level.
    st.subheader(f"📈 Queue Trends: {selected_clinic}")
    if not full_df.empty and "clinic_id" in full_df.columns:
        df_trends = full_df[full_df["clinic_id"] == selected_clinic].copy()
        df_trends["arrival_time"] = pd.to_datetime(df_trends["arrival_time"])
        df_trends.set_index("arrival_time", inplace=True)

        trend_data = df_trends.groupby([pd.Grouper(freq='1min'), 'priority']).size().unstack(fill_value=0)
        trend_data = trend_data.rolling(window=5).mean()

        st.line_chart(trend_data)
    

render_dashboard()