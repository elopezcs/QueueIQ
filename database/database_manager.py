import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

class DatabaseManager:
    def __init__(self: str):
        _ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
        load_dotenv(dotenv_path=_ENV_PATH, override=True)
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")

        if not all([db_user, db_password, db_host, db_port, db_name]):
            print(f"**Database environment variables are not fully set.** Expected DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME in {_ENV_PATH}.")
            exit(1)

        database_url = URL.create(
            drivername="postgresql",
            username=db_user,
            password=db_password,
            host=db_host,
            port=int(db_port),
            database=db_name,
        )

        self.engine = create_engine(database_url, pool_pre_ping=True)

    def init_db(self):
        with self.engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(:lock_key);"), {"lock_key": 22003130})
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clinics (
                    id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    address_or_city VARCHAR(100) NOT NULL
                );
            """))
            conn.execute(text("""
                INSERT INTO clinics (id, name, address_or_city)
                VALUES
                    ('kitchener-downtown', 'Kitchener Downtown', 'Kitchener, ON'),
                    ('waterloo-uptown', 'Waterloo Uptown', 'Waterloo, ON'),
                    ('waterloo-boardwalk', 'The Boardwalk', 'Kitchener, ON'),
                    ('kitchener-fairway', 'Fairway', 'Kitchener, ON'),
                    ('cambridge-hespeler', 'Cambridge Hespeler', 'Cambridge, ON')
                ON CONFLICT (name) DO NOTHING;
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clinic_queue (
                    record_id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    patient_id INTEGER NOT NULL,
                    arrival_time TIMESTAMP NOT NULL,
                    priority INTEGER NOT NULL,
                    est_duration INTEGER NOT NULL
                );
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS clinic_historical_data (
                    name VARCHAR(100) NOT NULL,
                    arrival_time TIMESTAMP NOT NULL,
                    day_of_week INTEGER NOT NULL,
                    day_sin DOUBLE PRECISION NOT NULL,
                    day_cos DOUBLE PRECISION NOT NULL,
                    is_weekend INTEGER NOT NULL,
                    hour_of_day INTEGER NOT NULL,
                    hour_sin DOUBLE PRECISION NOT NULL,
                    hour_cos DOUBLE PRECISION NOT NULL,
                    priority INTEGER NOT NULL,
                    est_duration INTEGER NOT NULL,
                    queue_length_at_arrival INTEGER NOT NULL,
                    arrivals_last_1_hour DOUBLE PRECISION NOT NULL,
                    avg_wait_last_1_hour DOUBLE PRECISION NOT NULL,
                    actual_wait_minutes DOUBLE PRECISION NOT NULL,
                    arrivals_next_2_hours DOUBLE PRECISION NOT NULL,
                    is_surge_imminent INTEGER NOT NULL
                );
            """))

    def fetch_queue(self) -> pd.DataFrame:
        query = text("""
            SELECT record_id, name, patient_id, arrival_time, priority, est_duration
            FROM clinic_queue
            ORDER BY name, priority ASC, arrival_time ASC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    def fetch_clinics(self) -> pd.DataFrame:
        query = text("""
            SELECT name
            FROM clinics
            ORDER BY name ASC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    def insert_patient(self, name: str, patient_id: int, arrival_time: pd.Timestamp, priority: int, est_duration: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO clinic_queue (name, patient_id, arrival_time, priority, est_duration)
                VALUES (:name, :patient_id, :arrival_time, :priority, :est_duration)
            """), {
                "name": name,
                "patient_id": patient_id,
                "arrival_time": arrival_time,
                "priority": priority,
                "est_duration": est_duration,
            })

    def delete_patient(self, record_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM clinic_queue
                WHERE record_id = :record_id
            """), {"record_id": record_id})


    def fetch_training_data(self, table_name) -> pd.DataFrame:
        query = text(f"SELECT * FROM {table_name}")
        with self.engine.connect() as conn:
            df = pd.read_sql_query(query, conn)

        if df.empty:
            raise ValueError(
                f"Table '{table_name}' is empty. Generate or load synthetic data before training the model."
            )

        return df
    
    def prepare_training_data_table(self, table_name):
        with self.engine.begin() as conn:
            conn.execute(text(f"DELETE FROM {table_name};"))