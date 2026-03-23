import random
import time
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text

# -----------------------------
# DATABASE
# -----------------------------
DATABASE_URL = "postgresql://neondb_owner:npg_ew9lIT7oOJMh@ep-super-bar-a8wl4ci7-pooler.eastus2.azure.neon.tech/neondb"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# -----------------------------
# CONFIG
# -----------------------------
CLINIC_CHOICES = ["Downtown-Clinic", "Uptown-Clinic", "Westside-Clinic"]

st.set_page_config(layout="wide", page_title="Multi-Clinic Dashboard")

# -----------------------------
# HELPERS
# -----------------------------
def load_data() -> pd.DataFrame:
    query = text("""
        SELECT record_id, clinic_id, patient_id, arrival_time, acuity, est_duration
        FROM clinic_queue
        ORDER BY clinic_id, acuity ASC, arrival_time ASC
    """)
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)

        if not df.empty:
            df["arrival_time"] = pd.to_datetime(df["arrival_time"])

        return df
    except Exception:
        return pd.DataFrame(columns=[
            "record_id", "clinic_id", "patient_id", "arrival_time", "acuity", "est_duration"
        ])


def add_patient_to_db(target_clinic: str, acuity: int | None = None):
    new_id = random.randint(1000, 9999)
    if acuity is None:
        acuity = random.choice([3, 4, 5])

    est_duration = {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[acuity]

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO clinic_queue (clinic_id, patient_id, arrival_time, acuity, est_duration)
            VALUES (:clinic_id, :patient_id, :arrival_time, :acuity, :est_duration)
        """), {
            "clinic_id": target_clinic,
            "patient_id": new_id,
            "arrival_time": datetime.now(),
            "acuity": acuity,
            "est_duration": est_duration
        })

    st.toast(f"✅ Patient {new_id} added to {target_clinic}!")


# -----------------------------
# UI
# -----------------------------
st.title("🏥 QueueIQ (CareFlow) Live Dashboard")

full_df = load_data()
selected_clinic = st.selectbox("📍 Select Clinic to View/Manage:", CLINIC_CHOICES)

if not full_df.empty and "clinic_id" in full_df.columns:
    df_waiting = full_df[full_df["clinic_id"] == selected_clinic].copy()
    total_waiting_system = len(full_df)
else:
    df_waiting = pd.DataFrame(columns=[
        "record_id", "clinic_id", "patient_id", "arrival_time", "acuity", "est_duration"
    ])
    total_waiting_system = 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Queue at {selected_clinic}", len(df_waiting))

if not df_waiting.empty:
    df_waiting = df_waiting.sort_values(by=["acuity", "arrival_time"])
    col2.metric("Next Up", int(df_waiting.iloc[0]["patient_id"]))
else:
    col2.metric("Next Up", "None")

col3.metric("Total System Queue (All Clinics)", total_waiting_system)
col4.caption("updates every 2s")

c_table, c_actions = st.columns([3, 1])

with c_table:
    st.subheader(f"📋 Current Queue: {selected_clinic}")

    if not df_waiting.empty:
        def highlight_critical(val):
            return "background-color: #ffcccc" if val == 1 else ""

        display_df = df_waiting.copy()
        display_df["arrival_time"] = display_df["arrival_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        display_df = display_df.drop(columns=["record_id", "clinic_id"], errors="ignore")

        st.dataframe(
            display_df.style.map(highlight_critical, subset=["acuity"]),
            width="stretch",
            hide_index=True
        )
    else:
        st.info(f"The waiting room at {selected_clinic} is empty.")

with c_actions:
    st.subheader("Reception Desk")
    st.write(f"Add patients to **{selected_clinic}**:")

    if st.button("➕ Add Standard Patient", key="btn_std"):
        add_patient_to_db(selected_clinic)

    if st.button("🚨 Add Critical (Acuity 1)", key="btn_crit"):
        add_patient_to_db(selected_clinic, acuity=1)

time.sleep(2)
st.rerun()