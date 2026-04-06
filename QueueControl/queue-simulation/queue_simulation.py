import importlib.util
import logging
import os
import random
import sys
import threading
import time
from datetime import datetime, timedelta
from html import escape

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

from database.database_manager import DatabaseManager

logger = logging.getLogger("queueiq.api")

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

QUEUE_COLUMNS = [
	"record_id",
	"clinic_name",
	"patient_id",
	"arrival_time",
	"priority",
	"est_duration",
]

GLOBAL_STYLES = """
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
"""


class QueueSimulationBackend:
	def __init__(self) -> None:
		self.db_manager = DatabaseManager()
		self.db_manager.init_db()

		self.clinic_names = self.db_manager.fetch_clinics()["clinic_name"].tolist()
		self.sim_config = {
			"num_doctors": 1,
			"sim_speed": 2.0,
			"use_rush_hour_predictor": True,
			"manual_rush_hour_probability": 50,
			"doctors_per_clinic": {clinic_name: 1 for clinic_name in self.clinic_names},
		}
		self.doctors_free_at = {clinic_name: [datetime.now()] for clinic_name in self.clinic_names}

		script_dir = os.path.dirname(os.path.abspath(__file__))
		self.model_path = os.path.abspath(
			os.path.join(script_dir, "..", "models", "rush_hour_predictor_model.joblib")
		)
		self.training_script_path = os.path.abspath(
			os.path.join(script_dir, "..", "model-training", "rush_hour_predictor_model.py")
		)
		self.rush_hour_predictor_model = joblib.load(self.model_path)

		self._simulation_thread: threading.Thread | None = None
		self._simulation_lock = threading.Lock()

	def retrain_rush_hour_model(self) -> None:
		spec = importlib.util.spec_from_file_location(
			"rush_hour_predictor_model", self.training_script_path
		)
		if spec is None or spec.loader is None:
			raise ImportError(f"Unable to load training script from {self.training_script_path}")

		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		module.train_model()
		self.rush_hour_predictor_model = joblib.load(self.model_path)

	@staticmethod
	def get_duration(priority: int) -> int:
		return {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]

	@staticmethod
	def create_empty_queue_df() -> pd.DataFrame:
		return pd.DataFrame(columns=QUEUE_COLUMNS)

	def prepare_queue_df(self, df: pd.DataFrame) -> pd.DataFrame:
		if df.empty:
			return self.create_empty_queue_df()

		prepared_df = df.copy()
		if "arrival_time" in prepared_df.columns:
			prepared_df["arrival_time"] = pd.to_datetime(prepared_df["arrival_time"])
		return prepared_df

	def build_clinic_queue_map(self, df: pd.DataFrame) -> dict[str, pd.DataFrame]:
		if df.empty or "clinic_name" not in df.columns:
			return {}

		return {
			clinic_name: clinic_df.sort_values(by=["priority", "arrival_time"]).reset_index(drop=True)
			for clinic_name, clinic_df in df.groupby("clinic_name", sort=False)
		}

	def get_model_surge_probability(
		self,
		queue_df: pd.DataFrame | None = None,
		now: datetime | None = None,
	) -> float:
		df = self.prepare_queue_df(self.db_manager.fetch_queue()) if queue_df is None else queue_df
		current_time = datetime.now() if now is None else now

		recent_patients = self.create_empty_queue_df()
		if not df.empty and "arrival_time" in df.columns:
			recent_patients = df[df["arrival_time"] >= (current_time - timedelta(hours=1))]

		avg_wait_last_1_hour = 0.0
		if not recent_patients.empty:
			avg_wait_last_1_hour = (
				(current_time - recent_patients["arrival_time"]).dt.total_seconds().mean() / 60.0
			)

		hour_of_day = current_time.hour
		day_of_week = current_time.weekday()

		features = pd.DataFrame([
			{
				"is_weekend": int(day_of_week >= 5),
				"day_sin": np.sin(2 * np.pi * day_of_week / 7.0),
				"day_cos": np.cos(2 * np.pi * day_of_week / 7.0),
				"hour_sin": np.sin(2 * np.pi * hour_of_day / 24.0),
				"hour_cos": np.cos(2 * np.pi * hour_of_day / 24.0),
				"queue_length_at_arrival": len(df),
				"arrivals_last_1_hour": len(recent_patients),
				"avg_wait_last_1_hour": avg_wait_last_1_hour,
			}
		])

		return round(float(self.rush_hour_predictor_model.predict_proba(features)[0][1]), 4)

	def get_surge_probability(
		self,
		queue_df: pd.DataFrame | None = None,
		now: datetime | None = None,
	) -> float:
		if not self.sim_config["use_rush_hour_predictor"]:
			return float(self.sim_config["manual_rush_hour_probability"]) / 100.0

		return self.get_model_surge_probability(queue_df=queue_df, now=now)

	def start_simulation_thread(self) -> None:
		with self._simulation_lock:
			if self._simulation_thread and self._simulation_thread.is_alive():
				return

			self._simulation_thread = threading.Thread(target=self.run_simulation, daemon=True)
			self._simulation_thread.start()

	def run_simulation(self) -> None:
		logger.info("--- BACKGROUND SIMULATION STARTED ---")

		while True:
			try:
				current_speed = self.sim_config["sim_speed"]

				df = self.prepare_queue_df(self.db_manager.fetch_queue())
				clinic_queue_map = self.build_clinic_queue_map(df)
				now = datetime.now()

				for clinic_name in self.clinic_names:
					current_doctors = int(self.sim_config["doctors_per_clinic"].get(clinic_name, 1))

					while len(self.doctors_free_at[clinic_name]) < current_doctors:
						self.doctors_free_at[clinic_name].append(now)
					while len(self.doctors_free_at[clinic_name]) > current_doctors:
						self.doctors_free_at[clinic_name].pop()

					waiting_patients = clinic_queue_map.get(clinic_name, self.create_empty_queue_df())

					for doctor_index in range(current_doctors):
						if now >= self.doctors_free_at[clinic_name][doctor_index] and not waiting_patients.empty:
							patient = waiting_patients.iloc[0]
							duration_sec = int(patient["est_duration"])
							self.doctors_free_at[clinic_name][doctor_index] = now + timedelta(
								seconds=duration_sec
							)

							self.db_manager.mark_patient_seen(int(patient["record_id"]))
							waited_min = (now - patient["arrival_time"]).total_seconds() / 60.0
							logger.info(
								f"[{clinic_name}] Doc {doctor_index + 1} took Patient {patient['patient_id']} "
								f"(waited {waited_min:.1f} min)"
							)

							waiting_patients = waiting_patients.iloc[1:]

				surge_prob = self.get_surge_probability(queue_df=df, now=now)
				current_prob = 0.05 + (surge_prob * 0.55)

				for clinic_name in self.clinic_names:
					if random.random() < current_prob:
						new_id = random.randint(1000, 9999)
						priority = random.choices([1, 2, 3, 4, 5], weights=[5, 10, 50, 25, 10])[0]
						self.db_manager.insert_patient(
							clinic_name,
							new_id,
							now,
							priority,
							self.get_duration(priority),
						)
						logger.info(
							f"Walk-in [{now.strftime('%H:%M:%S')}] {clinic_name}: Patient {new_id} added"
						)

				time.sleep(current_speed)

			except Exception as exc:
				logger.error(f"Simulation Error: {exc}")
				time.sleep(1)


@st.cache_resource
def get_backend() -> QueueSimulationBackend:
	return QueueSimulationBackend()


def setup_dashboard_page(page_title: str) -> None:
	st.set_page_config(
		layout="wide",
		page_title=page_title,
		page_icon="Q",
	)


def load_backend_or_stop() -> QueueSimulationBackend:
	try:
		backend = get_backend()
	except FileNotFoundError as exc:
		st.error(f"**Rush Hour Predictor model not found:** {exc}")
		st.stop()
	except Exception as exc:
		st.error(f"**Failed to initialize the simulator backend:** {exc}")
		st.stop()

	backend.start_simulation_thread()
	return backend


def inject_styles() -> None:
	st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


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
	display_df = display_df.drop(columns=["record_id", "clinic_name"], errors="ignore")
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


def render_sidebar(
	backend: QueueSimulationBackend,
	title: str,
	description: str,
	*,
	allow_add_patient: bool = False,
	allow_staffing: bool = False,
	allow_retrain: bool = False,
	allow_speed_control: bool = False,
) -> str:
	with st.sidebar:
		st.markdown(
			f"""
			<div class=\"sidebar-brand\">
			  <div class=\"sidebar-chip\">QueueIQ</div>
			  <h2>{escape(title)}</h2>
			  <p>{escape(description)}</p>
			</div>
			""",
			unsafe_allow_html=True,
		)

		try:
			sidebar_queue_df = backend.prepare_queue_df(backend.db_manager.fetch_queue())
			total_waiting_system = len(sidebar_queue_df)
		except Exception:
			sidebar_queue_df = backend.create_empty_queue_df()
			total_waiting_system = 0

		st.metric("Total system queue", total_waiting_system)

		selected_clinic = st.selectbox(
			"Clinic focus",
			backend.clinic_names,
			key=f"selected_clinic_{title}",
		)

		backend.sim_config["use_rush_hour_predictor"] = st.toggle(
			"Use rush hour predictor",
			value=backend.sim_config["use_rush_hour_predictor"],
			help="Turn the trained predictor on or switch to a manual rush hour probability.",
		)

		backend.sim_config["manual_rush_hour_probability"] = st.slider(
			"Manual rush hour probability (%)",
			min_value=0,
			max_value=100,
			value=int(backend.sim_config["manual_rush_hour_probability"]),
			step=1,
			disabled=backend.sim_config["use_rush_hour_predictor"],
			help="Available when the predictor is off. Sets the current rush hour probability manually.",
		)

		sidebar_surge_prob = backend.get_surge_probability(queue_df=sidebar_queue_df) * 100
		surge_outlook_text = (
			"Probability of an incoming surge based on the current queue and the trained predictor."
			if backend.sim_config["use_rush_hour_predictor"]
			else "Manual override is active. The simulator is using the percentage selected below."
		)
		st.markdown(
			f'''
			<div class="sidebar-note">
			  <span>Rush hour outlook</span>
			  <strong>{sidebar_surge_prob:.1f}%</strong>
			  <p>{escape(surge_outlook_text)}</p>
			</div>
			''',
			unsafe_allow_html=True,
		)

		if allow_retrain and st.button("Retrain rush hour model", key=f"btn_retrain_model_{title}"):
			with st.spinner("Retraining model. This may take a moment."):
				try:
					backend.retrain_rush_hour_model()
					st.success("Model retrained successfully.")
				except Exception as exc:
					st.error(f"Model retraining failed: {exc}")

		if allow_staffing:
			selected_clinic_doctors = int(backend.sim_config["doctors_per_clinic"].get(selected_clinic, 1))
			backend.sim_config["doctors_per_clinic"][selected_clinic] = st.slider(
				f"Doctors at {selected_clinic}",
				min_value=0,
				max_value=10,
				value=selected_clinic_doctors,
				step=1,
				help="Adjust staffing for the currently selected clinic only.",
			)

		if allow_speed_control:
			backend.sim_config["sim_speed"] = st.slider(
				"Update cadence (seconds)",
				min_value=0.5,
				max_value=10.0,
				value=backend.sim_config["sim_speed"],
				step=0.5,
				help="Controls how often the simulation loop and auto-refresh update.",
			)

		if allow_add_patient:
			selected_priority = st.selectbox(
				"Patient priority to add",
				options=list(PRIORITY_LABELS.keys()),
				format_func=lambda value: f"P{value} - {PRIORITY_LABELS[value]}",
				index=2,
			)

			if st.button("Add patient to selected clinic", key=f"btn_add_patient_{title}"):
				now = datetime.now()
				new_id = random.randint(1000, 9999)
				backend.db_manager.insert_patient(
					selected_clinic,
					new_id,
					now,
					selected_priority,
					backend.get_duration(selected_priority),
				)
				st.toast(
					f"Patient {new_id} added to {selected_clinic} at priority P{selected_priority}."
				)

	return selected_clinic


def get_dashboard_data(
	backend: QueueSimulationBackend,
	selected_clinic: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame, float]:
	try:
		full_df = backend.prepare_queue_df(backend.db_manager.fetch_queue())
	except Exception as exc:
		st.error(f"Database error: {exc}")
		full_df = backend.create_empty_queue_df()

	clinic_queue_map = backend.build_clinic_queue_map(full_df)
	df_waiting = clinic_queue_map.get(selected_clinic, backend.create_empty_queue_df()).copy()
	surge_prob = backend.get_surge_probability(queue_df=full_df)
	return full_df, clinic_queue_map, df_waiting, surge_prob


def render_dashboard_view(
	backend: QueueSimulationBackend,
	selected_clinic: str,
	*,
	badge: str,
	hero_title: str,
	hero_description: str,
	hero_panel_text: str,
	show_queue_table: bool,
	show_trends: bool,
) -> None:
	@st.fragment(run_every=timedelta(seconds=float(backend.sim_config["sim_speed"])))
	def _render_dashboard_fragment() -> None:
		st.markdown(
			f'''
			<div class="sim-hero">
			  <div>
				<div class="sim-hero-badge">{escape(badge)}</div>
				<h1>{escape(hero_title)}</h1>
				<p>{escape(hero_description)}</p>
			  </div>
			  <div class="sim-hero-panel">
				<span>Focused clinic</span>
				<strong>{escape(str(selected_clinic))}</strong>
				<p>{escape(hero_panel_text)}</p>
			  </div>
			</div>
			''',
			unsafe_allow_html=True,
		)

		_, clinic_queue_map, df_waiting, surge_prob = get_dashboard_data(backend, selected_clinic)
		next_up = format_next_up(df_waiting)
		avg_wait = format_average_wait(df_waiting)
		urgent_cases = int((df_waiting["priority"] <= 2).sum()) if not df_waiting.empty else 0

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

		if show_queue_table:
			main_cols = st.columns([1.8, 1.05])

			with main_cols[0]:
				render_section_heading(
					f"Current queue for {selected_clinic}"
				)
				if not df_waiting.empty:
					st.dataframe(
						build_queue_table(df_waiting),
						width="stretch",
						hide_index=True,
					)
				else:
					st.info(f"The waiting room at {selected_clinic} is currently empty.")

			with main_cols[1]:
				render_section_heading(
					"Surge monitor",
					"",
				)
				st.plotly_chart(build_surge_gauge(surge_prob), width="stretch")
		else:
			render_section_heading(
				"Surge monitor",
				"",
			)
			st.plotly_chart(build_surge_gauge(surge_prob), width="stretch")

		if show_trends:
			render_section_heading(
				f"Queue trends for {selected_clinic}",
				"Smoothed one-minute trends across priority bands to make flow shifts easier to read.",
			)

			df_trends = clinic_queue_map.get(selected_clinic, backend.create_empty_queue_df()).copy()
			if not df_trends.empty:
				df_trends.set_index("arrival_time", inplace=True)
				trend_data = build_trends_data(df_trends)
				if not trend_data.empty:
					st.line_chart(trend_data, width="stretch", height=360)
				else:
					st.info(f"No trend data is available yet for {selected_clinic}.")
			else:
				st.info(f"No trend data is available yet for {selected_clinic}.")

	_render_dashboard_fragment()


def main() -> None:
	setup_dashboard_page("QueueIQ Manager View")
	backend = load_backend_or_stop()
	inject_styles()
	selected_clinic = render_sidebar(
		backend,
		title="Manager View",
		description="Tune simulation controls, staffing, and prediction behavior while monitoring operational performance.",
		allow_staffing=True,
		allow_retrain=True,
		allow_speed_control=True,
	)
	render_dashboard_view(
		backend,
		selected_clinic,
		badge="Manager dashboard",
		hero_title="Supervise staffing and demand conditions",
		hero_description="Review live clinic pressure, adjust staffing for the selected site, and track queue trends with management controls.",
		hero_panel_text=(
			f"Auto-refresh every {backend.sim_config['sim_speed']:.1f} seconds with {backend.sim_config['doctors_per_clinic'].get(selected_clinic, 1)} doctor(s) assigned to this clinic."
		),
		show_queue_table=False,
		show_trends=True,
	)


if __name__ == "__main__":
	main()

