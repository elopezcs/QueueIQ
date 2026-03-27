import os
import time
import random
import threading
from datetime import datetime, timedelta

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(layout="wide", page_title="Multi-Clinic Dashboard")

# -----------------------------
# SHARED STATE (UI <-> THREAD)
# -----------------------------
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]

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
# DATABASE & ENVIRONMENT
# -----------------------------
_ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(dotenv_path=_ENV_PATH, override=True)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("**DATABASE_URL is not set.** Add it to your `.env` file, e.g.:\n\n`DATABASE_URL=postgresql://user:pass@localhost:5432/queueiq`")
    st.stop()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# -----------------------------
# MODEL
# -----------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.abspath(
    os.path.join(SCRIPT_DIR, "..", "models", "queueiq_xgb_model.joblib")
)

try:
    xgb_model = joblib.load(MODEL_PATH)
except FileNotFoundError:
    xgb_model = None

# -----------------------------
# BACKEND HELPERS
# -----------------------------
def get_duration(priority: int) -> int:
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clinic_queue (
                record_id SERIAL PRIMARY KEY,
                clinic_id VARCHAR(100) NOT NULL,
                patient_id INTEGER NOT NULL,
                arrival_time TIMESTAMP NOT NULL,
                priority INTEGER NOT NULL,
                est_duration INTEGER NOT NULL
            );
        """))

def fetch_queue() -> pd.DataFrame:
    query = text("""
        SELECT record_id, clinic_id, patient_id, arrival_time, priority, est_duration
        FROM clinic_queue
        ORDER BY clinic_id, priority ASC, arrival_time ASC
    """)
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn)

def insert_patient(clinic_id: str, patient_id: int, arrival_time: datetime, priority: int, est_duration: int):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO clinic_queue (clinic_id, patient_id, arrival_time, priority, est_duration)
            VALUES (:clinic_id, :patient_id, :arrival_time, :priority, :est_duration)
        """), {
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "arrival_time": arrival_time,
            "priority": priority,
            "est_duration": est_duration,
        })

def delete_patient(record_id: int):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM clinic_queue
            WHERE record_id = :record_id
        """), {"record_id": record_id})

def get_surge_probability(current_time: datetime, current_queue_length: int, arrivals_last_1h: int, avg_wait_last_1h: float) -> float:
    if xgb_model is None:
        return 0.05

    hour_of_day = current_time.hour
    day_of_week = current_time.weekday()
    
    features = pd.DataFrame([{
        "is_weekend": int(day_of_week >= 5),
        "day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
        "day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
        "hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
        "hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
        "queue_length_at_arrival": current_queue_length,
        "arrivals_last_1_hour": arrivals_last_1h,
        "avg_wait_last_1_hour": avg_wait_last_1h
    }])

    return round(float(xgb_model.predict_proba(features)[0][1]), 4)

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

            df = fetch_queue()
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

                            delete_patient(int(patient["record_id"]))
                            waited_min = (now - patient["arrival_time"]).total_seconds() / 60.0
                            print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['patient_id']} (waited {waited_min:.1f} min)")

                            waiting_patients = waiting_patients.iloc[1:]

            # 2. Dynamic arrivals
            df = fetch_queue()
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

                surge_prob = get_surge_probability(now, len(clinic_df), recent_arrivals, recent_wait)
                current_prob = 0.05 + (surge_prob * 0.55)

                if random.random() < current_prob:
                    new_id = random.randint(1000, 9999)
                    priority = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
                    insert_patient(cid, new_id, now, priority, get_duration(priority))
                    print(f"🔔 Walk-in [{now.strftime('%H:%M:%S')}] {cid}: Patient {new_id} added")

            # Pause based on the dynamic slider speed
            time.sleep(current_speed)

        except Exception as e:
            print(f"Simulation Error: {e}")
            time.sleep(1)

# Start thread only once
if "sim_thread_started" not in st.session_state:
    try:
        init_db()
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
    st.header("⚙️ Simulation Controls")
    
    sim_config["num_doctors"] = st.slider(
        "Doctors per Clinic", 
        min_value=0, max_value=10, value=sim_config["num_doctors"], step=1,
        help="Change this to dynamically add or remove doctors from the simulation."
    )
    
    sim_config["sim_speed"] = st.slider(
        "Simulation Speed (seconds/tick)", 
        min_value=0.5, max_value=10.0, value=sim_config["sim_speed"], step=0.5,
        help="Lower is faster. This controls how often the background loop runs."
    )
    
    if xgb_model is None:
        st.warning("⚠️ XGBoost model not loaded. Using fallback surge probabilities.")

# Main Dashboard
st.title("🏥 QueueIQ Live Dashboard")

try:
    full_df = fetch_queue()
    if not full_df.empty:
        full_df["arrival_time"] = pd.to_datetime(full_df["arrival_time"])
except Exception as e:
    st.error(f"Database error: {e}")
    full_df = pd.DataFrame()

selected_clinic = st.selectbox("📍 Select Clinic to View/Manage:", CLINIC_IDS)

if not full_df.empty and "clinic_id" in full_df.columns:
    df_waiting = full_df[full_df["clinic_id"] == selected_clinic].copy()
    total_waiting_system = len(full_df)
else:
    df_waiting = pd.DataFrame(columns=["record_id", "clinic_id", "patient_id", "arrival_time", "priority", "est_duration"])
    total_waiting_system = 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Queue at {selected_clinic}", len(df_waiting))

if not df_waiting.empty:
    df_waiting = df_waiting.sort_values(by=["priority", "arrival_time"])
    col2.metric("Next Up", int(df_waiting.iloc[0]["patient_id"]))
else:
    col2.metric("Next Up", "None")

col3.metric("Total System Queue (All Clinics)", total_waiting_system)
col4.caption(f"updates every {sim_config['sim_speed']}s")

c_table, c_actions = st.columns([3, 1])

with c_table:
    st.subheader(f"📋 Current Queue: {selected_clinic}")

    if not df_waiting.empty:
        display_df = df_waiting.copy()
        display_df["arrival_time"] = display_df["arrival_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df = display_df.drop(columns=["record_id", "clinic_id"], errors="ignore")
        
        st.dataframe(
            display_df.style.map(lambda v: "background-color: #ffcccc" if v == 1 else "", subset=["priority"]),
            width="stretch", hide_index=True
        )
    else:
        st.info(f"The waiting room at {selected_clinic} is empty.")

with c_actions:
    st.subheader("Reception Desk")
    st.write(f"Add patients to **{selected_clinic}**:")

    if st.button("➕ Add Standard Patient", key="btn_std"):
        new_id = random.randint(1000, 9999)
        priority = random.choice([3, 4, 5])
        insert_patient(selected_clinic, new_id, datetime.now(), priority, get_duration(priority))
        st.toast(f"✅ Patient {new_id} added!")

    if st.button("🚨 Add Critical (priority 1)", key="btn_crit"):
        new_id = random.randint(1000, 9999)
        insert_patient(selected_clinic, new_id, datetime.now(), 1, get_duration(1))
        st.toast(f"🚨 Critical Patient {new_id} added!")

# Streamlit UI Loop
time.sleep(sim_config["sim_speed"])
st.rerun()


# -----------------------------
# SHARED STATE (UI <-> THREAD)
# -----------------------------
CLINIC_IDS = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]

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
    os.path.join(SCRIPT_DIR, "..", "models", "queueiq_xgb_model.joblib")
)

try:
    xgb_model = joblib.load(MODEL_PATH)
except FileNotFoundError:
    xgb_model = None

# -----------------------------
# BACKEND HELPERS
# -----------------------------
def get_duration(priority: int) -> int:
    return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clinic_queue (
                record_id SERIAL PRIMARY KEY,
                clinic_id VARCHAR(100) NOT NULL,
                patient_id INTEGER NOT NULL,
                arrival_time TIMESTAMP NOT NULL,
                priority INTEGER NOT NULL,
                est_duration INTEGER NOT NULL
            );
        """))

def fetch_queue() -> pd.DataFrame:
    query = text("""
        SELECT record_id, clinic_id, patient_id, arrival_time, priority, est_duration
        FROM clinic_queue
        ORDER BY clinic_id, priority ASC, arrival_time ASC
    """)
    with engine.connect() as conn:
        return pd.read_sql_query(query, conn)

def insert_patient(clinic_id: str, patient_id: int, arrival_time: datetime, priority: int, est_duration: int):
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO clinic_queue (clinic_id, patient_id, arrival_time, priority, est_duration)
            VALUES (:clinic_id, :patient_id, :arrival_time, :priority, :est_duration)
        """), {
            "clinic_id": clinic_id,
            "patient_id": patient_id,
            "arrival_time": arrival_time,
            "priority": priority,
            "est_duration": est_duration,
        })

def delete_patient(record_id: int):
    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM clinic_queue
            WHERE record_id = :record_id
        """), {"record_id": record_id})

def get_surge_probability(current_time: datetime, current_queue_length: int, arrivals_last_1h: int, avg_wait_last_1h: float) -> float:
    if xgb_model is None:
        return 0.05

    hour_of_day = current_time.hour
    day_of_week = current_time.weekday()
    
    features = pd.DataFrame([{
        "is_weekend": int(day_of_week >= 5),
        "day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
        "day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
        "hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
        "hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
        "queue_length_at_arrival": current_queue_length,
        "arrivals_last_1_hour": arrivals_last_1h,
        "avg_wait_last_1_hour": avg_wait_last_1h
    }])

    return round(float(xgb_model.predict_proba(features)[0][1]), 4)

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

            df = fetch_queue()
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

                            delete_patient(int(patient["record_id"]))
                            waited_min = (now - patient["arrival_time"]).total_seconds() / 60.0
                            print(f"👨‍⚕️ [{cid}] Doc {i+1} took Patient {patient['patient_id']} (waited {waited_min:.1f} min)")

                            waiting_patients = waiting_patients.iloc[1:]

            # 2. Dynamic arrivals
            df = fetch_queue()
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

                surge_prob = get_surge_probability(now, len(clinic_df), recent_arrivals, recent_wait)
                current_prob = 0.05 + (surge_prob * 0.55)

                if random.random() < current_prob:
                    new_id = random.randint(1000, 9999)
                    priority = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
                    insert_patient(cid, new_id, now, priority, get_duration(priority))
                    print(f"🔔 Walk-in [{now.strftime('%H:%M:%S')}] {cid}: Patient {new_id} added")

            # Pause based on the dynamic slider speed
            time.sleep(current_speed)

        except Exception as e:
            print(f"Simulation Error: {e}")
            time.sleep(1)

# Start thread only once
if "sim_thread_started" not in st.session_state:
    try:
        init_db()
    except Exception as db_err:
        st.error(
            f"**Database connection failed.** The app cannot start without a database.\n\n"
            f"Ensure PostgreSQL is running and the connection URL is correct.\n\n"
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
    st.header("⚙️ Simulation Controls")
    
    # Update the shared dictionary directly from the sliders
    sim_config["num_doctors"] = st.slider(
        "Doctors per Clinic", 
        min_value=0, max_value=10, value=sim_config["num_doctors"], step=1,
        help="Change this to dynamically add or remove doctors from the simulation."
    )
    
    sim_config["sim_speed"] = st.slider(
        "Simulation Speed (seconds/tick)", 
        min_value=0.5, max_value=10.0, value=sim_config["sim_speed"], step=0.5,
        help="Lower is faster. This controls how often the background loop runs."
    )
    
    if xgb_model is None:
        st.warning("⚠️ XGBoost model not loaded. Using fallback surge probabilities.")

# Main Dashboard
st.title("🏥 QueueIQ Live Dashboard")

try:
    full_df = fetch_queue()
    if not full_df.empty:
        full_df["arrival_time"] = pd.to_datetime(full_df["arrival_time"])
except Exception as e:
    st.error(f"Database error: {e}")
    full_df = pd.DataFrame()

selected_clinic = st.selectbox("📍 Select Clinic to View/Manage:", CLINIC_IDS)

if not full_df.empty and "clinic_id" in full_df.columns:
    df_waiting = full_df[full_df["clinic_id"] == selected_clinic].copy()
    total_waiting_system = len(full_df)
else:
    df_waiting = pd.DataFrame(columns=["record_id", "clinic_id", "patient_id", "arrival_time", "priority", "est_duration"])
    total_waiting_system = 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Queue at {selected_clinic}", len(df_waiting))

if not df_waiting.empty:
    df_waiting = df_waiting.sort_values(by=["priority", "arrival_time"])
    col2.metric("Next Up", int(df_waiting.iloc[0]["patient_id"]))
else:
    col2.metric("Next Up", "None")

col3.metric("Total System Queue", total_waiting_system)
col4.caption("Dashboard updates automatically")

c_table, c_actions = st.columns([3, 1])

with c_table:
    st.subheader(f"📋 Current Queue: {selected_clinic}")

    if not df_waiting.empty:
        display_df = df_waiting.copy()
        display_df["arrival_time"] = display_df["arrival_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df = display_df.drop(columns=["record_id", "clinic_id"], errors="ignore")
        
        st.dataframe(
            display_df.style.map(lambda v: "background-color: #ffcccc" if v == 1 else "", subset=["priority"]),
            width="stretch", hide_index=True
        )
    else:
        st.info(f"The waiting room at {selected_clinic} is empty.")

with c_actions:
    st.subheader("Reception Desk")
    st.write(f"Add patients to **{selected_clinic}**:")

    if st.button("➕ Add Standard Patient", key="btn_std"):
        new_id = random.randint(1000, 9999)
        priority = random.choice([3, 4, 5])
        insert_patient(selected_clinic, new_id, datetime.now(), priority, get_duration(priority))
        st.toast(f"✅ Patient {new_id} added!")

    if st.button("🚨 Add Critical (priority 1)", key="btn_crit"):
        new_id = random.randint(1000, 9999)
        insert_patient(selected_clinic, new_id, datetime.now(), 1, get_duration(1))
        st.toast(f"🚨 Critical Patient {new_id} added!")

# Streamlit UI Loop
time.sleep(sim_config["sim_speed"])
st.rerun()