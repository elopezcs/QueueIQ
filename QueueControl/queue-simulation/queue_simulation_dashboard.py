import os
import sys
import time
import random
import threading
import importlib.util
from datetime import datetime, timedelta
from html import escape

import joblib
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import logging

logger = logging.getLogger("queueiq.api")

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
    st.error(f"**Failed to connect to the database:** {e}")
    st.stop()

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    layout="wide",
    page_title="QueueIQ Queue Simulator",
    page_icon="Q",
)

# -----------------------------
# THEME
# -----------------------------
PRIORITY_LABELS = {
    1: "Critical",
    2: "High",
    3: "Medium",
    4: "Low",
    5: "Very Low",
}

PRIORITY_COLORS = {
    1: "#ff7b54",
    2: "#ff9f43",
    3: "#03989e",
    4: "#005b96",
    5: "#8fa7c7",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --color-peach: #ff7b54;
          --color-water: #03989e;
          --color-azure: #005b96;
          --color-azure-dark: #004675;
          --color-air: #e8f1f2;
          --color-text: #2b2d42;
          --color-muted: #5f677d;
          --color-surface: #ffffff;
        }

        .stApp {
          background:
            radial-gradient(circle at top left, rgba(3, 152, 158, 0.12), transparent 32%),
            radial-gradient(circle at top right, rgba(0, 91, 150, 0.10), transparent 28%),
            linear-gradient(180deg, #f6f7fb 0%, #eef4f7 100%);
          color: var(--color-text);
        }

        .block-container {
          max-width: 1220px;
          padding-top: 2rem;
          padding-bottom: 2.5rem;
        }

        [data-testid="stSidebar"] {
          background: linear-gradient(180deg, #ffffff 0%, #f4f7f6 100%);
          border-right: 1px solid rgba(0, 91, 150, 0.08);
        }

        [data-testid="stSidebar"] .block-container {
          padding-top: 1.5rem;
        }

        .sidebar-brand {
          background: linear-gradient(135deg, var(--color-azure) 0%, var(--color-water) 100%);
          border-radius: 20px;
          padding: 1.25rem;
          color: #ffffff;
          margin-bottom: 1rem;
          box-shadow: 0 10px 28px rgba(0, 91, 150, 0.18);
        }

        .sidebar-chip {
          display: inline-block;
          padding: 0.3rem 0.7rem;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.18);
          font-size: 0.78rem;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          margin-bottom: 0.85rem;
        }

        .sidebar-brand h2 {
          margin: 0;
          font-size: 1.35rem;
          line-height: 1.2;
        }

        .sidebar-brand p {
          margin: 0.6rem 0 0;
          color: rgba(255, 255, 255, 0.92);
          line-height: 1.55;
          font-size: 0.95rem;
        }

        .sidebar-note {
          background: #ffffff;
          border: 1px solid #e8f1f2;
          border-radius: 16px;
          padding: 0.95rem 1rem;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
          margin: 0.9rem 0 1.1rem;
        }

        .sidebar-note span {
          display: block;
          color: var(--color-muted);
          font-size: 0.82rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.25rem;
        }

        .sidebar-note strong {
          display: block;
          color: var(--color-azure);
          font-size: 1.45rem;
          line-height: 1.2;
        }

        .sidebar-note p {
          margin: 0.45rem 0 0;
          color: var(--color-muted);
          font-size: 0.9rem;
          line-height: 1.45;
        }

        .sim-hero {
          background: linear-gradient(135deg, var(--color-azure) 0%, var(--color-water) 100%);
          border-radius: 24px;
          padding: 2rem;
          color: #ffffff;
          display: grid;
          grid-template-columns: minmax(0, 2.2fr) minmax(260px, 1fr);
          gap: 1.4rem;
          box-shadow: 0 16px 36px rgba(0, 91, 150, 0.18);
          margin-bottom: 1.5rem;
        }

        .sim-hero-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          padding: 0.42rem 0.8rem;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.16);
          font-size: 0.82rem;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          margin-bottom: 0.95rem;
        }

        .sim-hero h1 {
          margin: 0;
          font-size: 2.25rem;
          line-height: 1.08;
        }

        .sim-hero p {
          margin: 0.95rem 0 0;
          max-width: 56rem;
          font-size: 1rem;
          line-height: 1.7;
          color: rgba(255, 255, 255, 0.92);
        }

        .sim-hero-panel {
          background: rgba(255, 255, 255, 0.12);
          border: 1px solid rgba(255, 255, 255, 0.18);
          border-radius: 18px;
          padding: 1.15rem;
          backdrop-filter: blur(10px);
          align-self: stretch;
        }

        .sim-hero-panel span {
          display: block;
          color: rgba(255, 255, 255, 0.78);
          font-size: 0.8rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.35rem;
        }

        .sim-hero-panel strong {
          display: block;
          font-size: 1.7rem;
          line-height: 1.15;
          margin-bottom: 0.55rem;
        }

        .sim-hero-panel p {
          margin: 0;
          font-size: 0.92rem;
          line-height: 1.55;
        }

        .section-heading-wrap {
          margin: 0.35rem 0 0.8rem;
        }

        .section-heading {
          margin: 0;
          color: var(--color-azure);
          font-size: 1.35rem;
          line-height: 1.2;
        }

        .section-subtitle {
          margin: 0.35rem 0 0;
          color: var(--color-muted);
          font-size: 0.95rem;
          line-height: 1.55;
        }

        .metric-shell {
          background: var(--color-surface);
          border-radius: 18px;
          border: 1px solid #e8f1f2;
          border-top: 4px solid var(--color-azure);
          padding: 1.05rem 1.1rem;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
          min-height: 132px;
        }

        .metric-water { border-top-color: var(--color-water); }
        .metric-peach { border-top-color: var(--color-peach); }
        .metric-air { border-top-color: #8fa7c7; }

        .metric-label {
          color: var(--color-muted);
          font-size: 0.82rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.45rem;
        }

        .metric-value {
          color: var(--color-azure);
          font-size: 1.9rem;
          font-weight: 700;
          line-height: 1.1;
          margin-bottom: 0.4rem;
        }

        .metric-caption {
          color: var(--color-muted);
          font-size: 0.93rem;
          line-height: 1.45;
        }

        div[data-testid="stMetric"] {
          background: #ffffff;
          border: 1px solid #e8f1f2;
          border-radius: 16px;
          padding: 0.9rem 1rem;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
        }

        div[data-testid="stMetricLabel"] {
          color: var(--color-muted);
          font-weight: 600;
        }

        div[data-testid="stMetricValue"] {
          color: var(--color-azure);
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stPlotlyChart"] {
          background: #ffffff;
          border: 1px solid #e8f1f2;
          border-radius: 18px;
          padding: 0.9rem;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
        }

        .stButton > button {
          width: 100%;
          border-radius: 12px;
          border: 1px solid var(--color-azure);
          background: var(--color-azure);
          color: #ffffff;
          font-weight: 600;
          padding: 0.7rem 1rem;
          transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
        }

        .stButton > button:hover {
          background: var(--color-azure-dark);
          border-color: var(--color-azure-dark);
          transform: translateY(-1px);
        }

        .stButton > button:focus {
          box-shadow: 0 0 0 0.2rem rgba(0, 91, 150, 0.18);
        }

        div[data-baseweb="select"] > div,
        .stTextInput input,
        .stNumberInput input {
          border-radius: 12px !important;
          border-color: #d7dfe5 !important;
          background: #ffffff !important;
        }

        .stSlider [data-baseweb="slider"] {
          padding-top: 0.35rem;
        }

        .stSlider [role="slider"] {
          background-color: var(--color-azure);
          border-color: var(--color-azure);
        }

        .stAlert {
          border-radius: 14px;
        }

        @media (max-width: 900px) {
          .sim-hero {
            grid-template-columns: 1fr;
            padding: 1.5rem;
          }

          .sim-hero h1 {
            font-size: 1.85rem;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# SHARED STATE (UI <-> THREAD)
# -----------------------------
CLINIC_IDS = db_manager.fetch_clinics()["clinic_id"].tolist()


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
    os.path.join(SCRIPT_DIR, "..", "model-training", "rush_hour_predictor_model.py")
)

try:
    rush_hour_predictor_model = joblib.load(MODEL_PATH)
except FileNotFoundError:
    st.error(f"**Rush Hour Predictor model not found at {MODEL_PATH}.** Please ensure the model exists.")
    st.stop()


# -----------------------------
# HELPERS
# -----------------------------
def retrain_rush_hour_model() -> None:
    global rush_hour_predictor_model

    spec = importlib.util.spec_from_file_location("rush_hour_predictor_model", TRAINING_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load training script from {TRAINING_SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.train_model()
    rush_hour_predictor_model = joblib.load(MODEL_PATH)


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

    features = pd.DataFrame([
        {
            "is_weekend": int(day_of_week >= 5),
            "day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
            "day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
            "hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
            "hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
            "queue_length_at_arrival": len(clinic_df),
            "arrivals_last_1_hour": recent_arrivals,
            "avg_wait_last_1_hour": recent_wait,
        }
    ])

    rush_hour_probability = round(float(rush_hour_predictor_model.predict_proba(features)[0][1]), 4)
    return rush_hour_probability


def format_next_up(df_waiting: pd.DataFrame) -> str:
    if df_waiting.empty:
        return "None"
    return str(int(df_waiting.iloc[0]["patient_id"]))


def format_average_wait(df_waiting: pd.DataFrame) -> str:
    if df_waiting.empty:
        return "0m"

    avg_minutes = float(
        ((datetime.now() - df_waiting["arrival_time"]).dt.total_seconds() / 60.0).mean()
    )
    total_minutes = max(0, int(round(avg_minutes)))
    hours, minutes = divmod(total_minutes, 60)

    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"



def priority_cell_style(value: object) -> str:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return ""

    color = PRIORITY_COLORS.get(priority, "#8fa7c7")
    return (
        f"background-color: {color}22; color: #223; font-weight: 600; "
        f"border-left: 4px solid {color}; border-radius: 8px;"
    )


def build_queue_table(df_waiting: pd.DataFrame):
    display_df = df_waiting.copy()
    display_df["arrival_time"] = display_df["arrival_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    display_df["urgency"] = display_df["priority"].map(PRIORITY_LABELS)
    display_df = display_df.drop(columns=["record_id", "clinic_id"], errors="ignore")
    display_df = display_df.rename(
        columns={
            "patient_id": "Patient ID",
            "arrival_time": "Arrival Time",
            "priority": "Priority",
            "est_duration": "Est. Duration",
            "urgency": "Urgency",
        }
    )

    ordered_columns = ["Patient ID", "Priority", "Urgency", "Arrival Time", "Est. Duration"]
    display_df = display_df[[col for col in ordered_columns if col in display_df.columns]]

    return display_df.style.format(
        {
            "Priority": lambda value: f"P{int(value)}",
            "Est. Duration": lambda value: f"{int(value)} sec",
        }
    ).map(priority_cell_style, subset=["Priority"])


def build_surge_gauge(surge_prob: float) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=surge_prob * 100,
            number={"suffix": "%", "font": {"size": 34, "color": "#005b96"}},
            title={"text": "Rush Hour Probability", "font": {"size": 18, "color": "#2b2d42"}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#7b8397"},
                "bar": {"color": "#005b96", "thickness": 0.3},
                "bgcolor": "white",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 45], "color": "#dff4ef"},
                    {"range": [45, 75], "color": "#ffe5cc"},
                    {"range": [75, 100], "color": "#ffd7ce"},
                ],
            },
        )
    )
    fig.update_layout(
        height=320,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        font={"family": "Segoe UI, Arial, sans-serif"},
    )
    return fig


def build_trends_data(df_trends: pd.DataFrame) -> pd.DataFrame:
    trend_data = df_trends.groupby([pd.Grouper(freq="1min"), "priority"]).size().unstack(fill_value=0)
    trend_data = trend_data.rolling(window=5, min_periods=1).mean()
    trend_data = trend_data.rename(
        columns={
            priority: f"P{priority} - {PRIORITY_LABELS.get(priority, 'Unknown')}"
            for priority in trend_data.columns
        }
    )
    return trend_data


def build_trends_chart(df_trends: pd.DataFrame) -> go.Figure:
    trend_data = df_trends.groupby([pd.Grouper(freq="1min"), "priority"]).size().unstack(fill_value=0)
    trend_data = trend_data.rolling(window=5, min_periods=1).mean()

    fig = go.Figure()
    for priority in sorted(trend_data.columns):
        fig.add_trace(
            go.Scatter(
                x=trend_data.index,
                y=trend_data[priority],
                mode="lines",
                name=f"P{priority} - {PRIORITY_LABELS.get(priority, 'Unknown')}",
                line={"width": 3, "color": PRIORITY_COLORS.get(priority, "#8fa7c7")},
            )
        )

    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        hovermode="x unified",
        font={"family": "Segoe UI, Arial, sans-serif", "color": "#2b2d42"},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
        xaxis={
            "title": "Time",
            "showgrid": False,
            "linecolor": "#d7dfe5",
        },
        yaxis={
            "title": "Patients",
            "gridcolor": "#edf1f5",
            "zeroline": False,
        },
    )
    return fig


def render_section_heading(title: str, subtitle: str = "") -> None:
    subtitle_html = f'<p class="section-subtitle">{escape(subtitle)}</p>' if subtitle else ""
    st.markdown(
        f'''
        <div class="section-heading-wrap">
          <h2 class="section-heading">{escape(title)}</h2>
          {subtitle_html}
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_metric_card(title: str, value: str, caption: str, accent: str = "") -> None:
    accent_class = f" metric-{accent}" if accent else ""
    st.markdown(
        f'''
        <div class="metric-shell{accent_class}">
          <div class="metric-label">{escape(title)}</div>
          <div class="metric-value">{escape(str(value))}</div>
          <div class="metric-caption">{escape(caption)}</div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


# -----------------------------
# BACKGROUND SIMULATION THREAD
# -----------------------------
def run_simulation() -> None:
    logger.info("--- BACKGROUND SIMULATION STARTED ---")

    while True:
        try:
            current_doctors = sim_config["num_doctors"]
            current_speed = sim_config["sim_speed"]

            df = db_manager.fetch_queue()
            now = datetime.now()

            if not df.empty:
                df["arrival_time"] = pd.to_datetime(df["arrival_time"])

                for cid in CLINIC_IDS:
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
                            logger.info(
                                f"[{cid}] Doc {i + 1} took Patient {patient['patient_id']} "
                                f"(waited {waited_min:.1f} min)"
                            )

                            waiting_patients = waiting_patients.iloc[1:]

                surge_prob = get_surge_probability()
                current_prob = 0.05 + (surge_prob * 0.55)

                if random.random() < current_prob:
                    new_id = random.randint(1000, 9999)
                    priority = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
                    db_manager.insert_patient(cid, new_id, now, priority, get_duration(priority))
                    logger.info(
                        f"Walk-in [{now.strftime('%H:%M:%S')}] {cid}: Patient {new_id} added"
                    )

            time.sleep(current_speed)

        except Exception as e:
            logger.error(f"Simulation Error: {e}")
            time.sleep(1)


# Start thread only once
if "sim_thread_started" not in st.session_state:
    try:
        db_manager = DatabaseManager()
        db_manager.init_db()
    except Exception as db_err:
        st.error(
            "**Database connection failed.** Ensure PostgreSQL is running and `DATABASE_URL` in `.env` is correct.\n\n"
            f"Error: `{db_err}`"
        )
        st.stop()
    sim_thread = threading.Thread(target=run_simulation, daemon=True)
    sim_thread.start()
    st.session_state.sim_thread_started = True


# -----------------------------
# FRONTEND UI
# -----------------------------
inject_styles()

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <div class="sidebar-chip">QueueIQ</div>
          <h2>QueueControl Simulator</h2>
          <p>Manage the live simulation with the same calm, structured visual language used across the chatbot experience.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        sidebar_queue_df = db_manager.fetch_queue()
        total_waiting_system = len(sidebar_queue_df)
    except Exception:
        total_waiting_system = 0

    st.metric("Total system queue", total_waiting_system)

    selected_clinic = st.selectbox(
        "Clinic focus",
        CLINIC_IDS,
        key="selected_clinic",
    )

    sidebar_surge_prob = get_surge_probability() * 100
    st.markdown(
        f'''
        <div class="sidebar-note">
          <span>Rush hour outlook</span>
          <strong>{sidebar_surge_prob:.1f}%</strong>
          <p>Probability of an incoming surge based on the current queue and the trained predictor.</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if st.button("Retrain rush hour model", key="btn_retrain_model"):
        with st.spinner("Retraining model. This may take a moment."):
            try:
                retrain_rush_hour_model()
                st.success("Model retrained successfully.")
            except Exception as e:
                st.error(f"Model retraining failed: {e}")

    sim_config["num_doctors"] = st.slider(
        "Doctors per clinic",
        min_value=0,
        max_value=10,
        value=sim_config["num_doctors"],
        step=1,
        help="Dynamically add or remove doctors from the active simulation.",
    )

    sim_config["sim_speed"] = st.slider(
        "Update cadence (seconds)",
        min_value=0.5,
        max_value=10.0,
        value=sim_config["sim_speed"],
        step=0.5,
        help="Controls how often the simulation loop and auto-refresh update.",
    )

    selected_priority = st.selectbox(
        "Patient priority to add",
        options=list(PRIORITY_LABELS.keys()),
        format_func=lambda value: f"P{value} - {PRIORITY_LABELS[value]}",
        index=2,
    )

    if st.button("Add patient to all clinics", key="btn_add_patient_all"):
        now = datetime.now()
        for cid in CLINIC_IDS:
            new_id = random.randint(1000, 9999)
            db_manager.insert_patient(cid, new_id, now, selected_priority, get_duration(selected_priority))
        st.toast(f"Patient batch added across all clinics at priority P{selected_priority}.")


@st.fragment(run_every=timedelta(seconds=float(sim_config["sim_speed"])))
def render_dashboard() -> None:
    st.markdown(
        f'''
        <div class="sim-hero">
          <div>
            <div class="sim-hero-badge">QueueControl simulator</div>
            <h1>Live multi-clinic operations dashboard</h1>
            <p>
              Monitor patient flow, staffing pressure, and queue movement in a layout aligned with
              the QueueIQ chatbot and website design system.
            </p>
          </div>
          <div class="sim-hero-panel">
            <span>Focused clinic</span>
            <strong>{escape(str(selected_clinic))}</strong>
            <p>Auto-refresh every {sim_config['sim_speed']:.1f} seconds with {sim_config['num_doctors']} doctor(s) per clinic.</p>
          </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )

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

    if not df_waiting.empty:
        df_waiting = df_waiting.sort_values(by=["priority", "arrival_time"])

    next_up = format_next_up(df_waiting)
    avg_wait = format_average_wait(df_waiting)
    urgent_cases = int((df_waiting["priority"] <= 2).sum()) if not df_waiting.empty else 0
    surge_prob = get_surge_probability()

    metric_cols = st.columns(4)
    with metric_cols[0]:
        render_metric_card(
            "Queue at selected clinic",
            str(len(df_waiting)),
            "Patients currently waiting in the active clinic view.",
        )
    with metric_cols[1]:
        render_metric_card(
            "Next up",
            next_up,
            "The next patient expected to be served based on current ordering.",
            accent="water",
        )
    with metric_cols[2]:
        render_metric_card(
            "Average wait",
            avg_wait,
            "Calculated from the current queue only and refreshed with the simulator.",
            accent="peach",
        )
    with metric_cols[3]:
        render_metric_card(
            "Urgent cases",
            str(urgent_cases),
            "Patients at priority P1 or P2 currently in the selected clinic.",
            accent="air",
        )

    main_cols = st.columns([1.8, 1.05])

    with main_cols[0]:
        render_section_heading(
            f"Current queue for {selected_clinic}",
            "A clean operational queue view using the same white-surface card treatment as the Chatbot pages.",
        )
        if not df_waiting.empty:
            st.dataframe(
                build_queue_table(df_waiting),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(f"The waiting room at {selected_clinic} is currently empty.")

    with main_cols[1]:
        render_section_heading(
            "Surge monitor",
            "Live risk indicator styled with the QueueIQ palette.",
        )
        st.plotly_chart(build_surge_gauge(surge_prob), use_container_width=True)

    render_section_heading(
        f"Queue trends for {selected_clinic}",
        "Smoothed one-minute trends across priority bands to make flow shifts easier to read.",
    )

    if not full_df.empty and "clinic_id" in full_df.columns:
        df_trends = full_df[full_df["clinic_id"] == selected_clinic].copy()
        if not df_trends.empty:
            df_trends["arrival_time"] = pd.to_datetime(df_trends["arrival_time"])
            df_trends.set_index("arrival_time", inplace=True)
            trend_data = build_trends_data(df_trends)
            if not trend_data.empty:
                st.line_chart(trend_data, use_container_width=True, height=360)
            else:
                st.info(f"No trend data is available yet for {selected_clinic}.")
        else:
            st.info(f"No trend data is available yet for {selected_clinic}.")
    else:
        st.info("Trend data will appear once patients start entering the queue.")


render_dashboard()

