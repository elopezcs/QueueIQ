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
                    clinic_id VARCHAR(100) PRIMARY KEY,
                    clinic_name VARCHAR(100) NOT NULL UNIQUE,
                    city VARCHAR(100) NOT NULL, 
                    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.execute(text("""
                INSERT INTO clinics (clinic_id, clinic_name, city, timezone, created_at)
                VALUES
                    ('kitchener-downtown', 'Kitchener Downtown', 'Kitchener, ON', 'America/Toronto', CURRENT_TIMESTAMP),
                    ('waterloo-uptown', 'Waterloo Uptown', 'Waterloo, ON', 'America/Toronto', CURRENT_TIMESTAMP),
                    ('waterloo-boardwalk', 'The Boardwalk', 'Kitchener, ON', 'America/Toronto', CURRENT_TIMESTAMP),
                    ('kitchener-fairway', 'Fairway', 'Kitchener, ON', 'America/Toronto', CURRENT_TIMESTAMP),
                    ('cambridge-hespeler', 'Cambridge Hespeler', 'Cambridge, ON', 'America/Toronto', CURRENT_TIMESTAMP)
                ON CONFLICT (clinic_name) DO NOTHING;
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS clinic_queue (
                    record_id SERIAL PRIMARY KEY,
                    clinic_name VARCHAR(100) NOT NULL,
                    patient_id INTEGER NOT NULL,
                    arrival_time TIMESTAMP NOT NULL,
                    priority INTEGER NOT NULL,
                    est_duration INTEGER NOT NULL,
                    seen_by_doctor_time TIMESTAMP NULL
                );
            """))
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS clinic_historical_data (
                    clinic_id VARCHAR(100) NOT NULL,
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
                    is_surge_imminent INTEGER NOT NULL,
                    CONSTRAINT fk_clinic_historical_data_clinic
                        FOREIGN KEY (clinic_id) REFERENCES clinics (clinic_id)
                );
            """))
            conn.execute(text("""
                ALTER TABLE clinic_queue
                ADD COLUMN IF NOT EXISTS seen_by_doctor_time TIMESTAMP NULL;
            """))
            conn.execute(text("""
                ALTER TABLE clinic_historical_data
                ADD COLUMN IF NOT EXISTS clinic_id VARCHAR(100);
            """))
            conn.execute(text("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'clinic_historical_data'
                          AND column_name = 'clinic_name'
                    ) THEN
                        UPDATE clinic_historical_data AS historical
                        SET clinic_id = clinics.clinic_id
                        FROM clinics
                        WHERE historical.clinic_id IS NULL
                          AND historical.clinic_name = clinics.clinic_name;

                        ALTER TABLE clinic_historical_data
                        ALTER COLUMN clinic_name DROP NOT NULL;
                    END IF;
                END
                $$;
            """))

    def fetch_queue(self) -> pd.DataFrame:
        query = text("""
            SELECT record_id, clinic_name, patient_id, arrival_time, priority, est_duration
            FROM clinic_queue
            WHERE seen_by_doctor_time IS NULL
            ORDER BY clinic_name, priority ASC, arrival_time ASC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    def fetch_queue_activity(self) -> pd.DataFrame:
        query = text("""
            SELECT record_id, clinic_name, patient_id, arrival_time, priority, est_duration, seen_by_doctor_time
            FROM clinic_queue
            ORDER BY clinic_name, arrival_time ASC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    def fetch_clinics(self) -> pd.DataFrame:
        query = text("""
            SELECT clinic_id, clinic_name
            FROM clinics 
            ORDER BY clinic_name ASC
        """)
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    def insert_patient(self, clinic_name: str, patient_id: int, arrival_time: pd.Timestamp, priority: int, est_duration: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO clinic_queue (clinic_name, patient_id, arrival_time, priority, est_duration, seen_by_doctor_time)
                VALUES (:clinic_name, :patient_id, :arrival_time, :priority, :est_duration, NULL)
            """), {
                "clinic_name": clinic_name,
                "patient_id": patient_id,
                "arrival_time": arrival_time,
                "priority": priority,
                "est_duration": est_duration,
            })

    def mark_patient_seen(self, record_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE clinic_queue
                SET seen_by_doctor_time = CURRENT_TIMESTAMP
                WHERE record_id = :record_id
            """), {"record_id": record_id})

    def delete_queue_record(self, record_id: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM clinic_queue
                WHERE record_id = :record_id
            """), {"record_id": record_id})

    def update_patient_triage(self, record_id: int, priority: int, est_duration: int):
        with self.engine.begin() as conn:
            conn.execute(text("""
                UPDATE clinic_queue
                SET priority = :priority,
                    est_duration = :est_duration
                WHERE record_id = :record_id
                  AND seen_by_doctor_time IS NULL
            """), {
                "record_id": record_id,
                "priority": priority,
                "est_duration": est_duration,
            })


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
