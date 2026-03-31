import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
import os
import sys
import logging

logger = logging.getLogger("queueiq.api")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from database.database_manager import DatabaseManager

@dataclass(slots=True)
class ClinicalAnnualVisitsConfig:
    table_name: str = "clinic_historical_data"
    num_doctors: int = 2
    days_to_simulate: int = 365
    start_date: datetime = datetime(2023, 1, 1, 8, 0, 0)


class ClinicalAnnualVisitsGenerator:
    def __init__(
        self,
        db_manager: DatabaseManager | None = None,
        config: ClinicalAnnualVisitsConfig | None = None,
        app_logger: logging.Logger | None = None,
    ):
        self.logger = app_logger or logger
        self.config = config or ClinicalAnnualVisitsConfig()
        self.db_manager = db_manager or self._create_db_manager()
        self.clinic_ids = self.db_manager.fetch_clinics()["clinic_id"].tolist()

    def _create_db_manager(self) -> DatabaseManager:
        try:
            manager = DatabaseManager()
            manager.init_db()
            return manager
        except Exception as exc:
            self.logger.error(f"**❌ Failed to connect to the database:** {exc}")
            raise

    def persist_generated_data(self, df_final: pd.DataFrame) -> None:
        self.db_manager.prepare_training_data_table(self.config.table_name)
        df_final.to_sql(
            self.config.table_name,
            self.db_manager.engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=1000,
        )

    def get_duration(self, priority: int) -> int:
        base = {1: 60, 2: 40, 3: 20, 4: 10, 5: 5}[priority]
        noise = np.random.normal(0, 3)
        return max(1, int(base + noise))

    def generate_arrivals(self) -> pd.DataFrame:
        self.logger.info(f"⚙️ Generating {self.config.days_to_simulate} days of synthetic history...")
        all_visits: list[dict[str, object]] = []

        for day in range(self.config.days_to_simulate):
            current_date = self.config.start_date + timedelta(days=day)
            is_weekend = current_date.weekday() >= 5

            for clinic in self.clinic_ids:
                for hour in range(8, 20):
                    rate = self._get_hourly_arrival_rate(hour, is_weekend)
                    num_arrivals = np.random.poisson(rate)

                    for _ in range(num_arrivals):
                        minute = np.random.randint(0, 60)
                        arrival_time = current_date.replace(hour=hour, minute=minute)
                        priority = np.random.choice([1, 2, 3, 4, 5], p=[0.05, 0.10, 0.50, 0.25, 0.10])

                        all_visits.append({
                            "clinic_id": clinic,
                            "arrival_time": arrival_time,
                            "day_of_week": current_date.weekday(),
                            "is_weekend": int(is_weekend),
                            "hour_of_day": hour,
                            "priority": priority,
                            "est_duration": self.get_duration(int(priority)),
                        })

        df_visits = pd.DataFrame(all_visits)
        return df_visits.sort_values(by=["clinic_id", "arrival_time"]).reset_index(drop=True)

    def _get_hourly_arrival_rate(self, hour: int, is_weekend: bool) -> int:
        if 8 <= hour < 11:
            rate = 8
        elif 11 <= hour < 14:
            rate = 3
        elif 16 <= hour < 19:
            rate = 10
        else:
            rate = 4

        if is_weekend:
            rate = int(rate * 1.2)

        return rate

    def simulate_queue(self, df_visits: pd.DataFrame) -> pd.DataFrame:
        self.logger.info(f"📊 Processing queue dynamics for {len(df_visits)} visits...")
        final_data: list[dict[str, object]] = []

        for clinic in self.clinic_ids:
            clinic_data = df_visits[df_visits["clinic_id"] == clinic].to_dict("records")
            doctors_free_at = [self.config.start_date] * self.config.num_doctors
            queue_history: list[tuple[datetime, datetime]] = []

            for visit in clinic_data:
                arrival_time = visit["arrival_time"]
                queue_length = sum(1 for hist_arrival, hist_start in queue_history if hist_arrival <= arrival_time and hist_start > arrival_time)
                visit["queue_length_at_arrival"] = queue_length

                doctors_free_at.sort()
                earliest_free = doctors_free_at[0]

                if earliest_free <= arrival_time:
                    start_time = arrival_time
                    wait_minutes = 0.0
                else:
                    start_time = earliest_free
                    wait_minutes = (start_time - arrival_time).total_seconds() / 60.0

                doctors_free_at[0] = start_time + timedelta(minutes=visit["est_duration"])
                queue_history.append((arrival_time, start_time))

                visit["actual_wait_minutes"] = round(wait_minutes, 1)
                final_data.append(visit)

        return pd.DataFrame(final_data)

    def engineer_features(self, df_final: pd.DataFrame) -> pd.DataFrame:
        self.logger.info("🧠 Engineering features for model training...")

        df_final = df_final.copy()
        df_final["hour_sin"] = np.sin(2 * np.pi * df_final["hour_of_day"] / 24.0)
        df_final["hour_cos"] = np.cos(2 * np.pi * df_final["hour_of_day"] / 24.0)
        df_final["day_sin"] = np.sin(2 * np.pi * df_final["day_of_week"] / 7.0)
        df_final["day_cos"] = np.cos(2 * np.pi * df_final["day_of_week"] / 7.0)

        df_final = df_final.sort_values(by=["clinic_id", "arrival_time"]).reset_index(drop=True)
        df_final = df_final.set_index("arrival_time")

        lagged_arrivals = []
        lagged_wait_time = []

        for clinic in self.clinic_ids:
            clinic_df = df_final[df_final["clinic_id"] == clinic].copy()
            past_1h_counts = clinic_df["clinic_id"].rolling("1h", closed="left").count().fillna(0)
            past_1h_wait = clinic_df["actual_wait_minutes"].rolling("1h", closed="left").mean().fillna(0)
            lagged_arrivals.extend(past_1h_counts.tolist())
            lagged_wait_time.extend(past_1h_wait.tolist())

        df_final = df_final.reset_index()
        df_final["arrivals_last_1_hour"] = lagged_arrivals
        df_final["avg_wait_last_1_hour"] = lagged_wait_time
        return df_final

    def calculate_targets(self, df_final: pd.DataFrame) -> pd.DataFrame:
        self.logger.info("⏳ Calculating surge prediction targets...")

        df_final = df_final.copy().set_index("arrival_time")
        arrivals_next_2h = []

        for clinic in self.clinic_ids:
            clinic_df = df_final[df_final["clinic_id"] == clinic].copy()
            future_counts = clinic_df["clinic_id"].rolling("2h").count().shift(-1).fillna(0)
            arrivals_next_2h.extend(future_counts.tolist())

        df_final = df_final.reset_index()
        df_final["arrivals_next_2_hours"] = arrivals_next_2h
        df_final["is_surge_imminent"] = (df_final["arrivals_next_2_hours"] > 15).astype(int)
        return df_final

    def finalize_dataset(self, df_final: pd.DataFrame) -> pd.DataFrame:
        columns = [
            "clinic_id", "arrival_time",
            "day_of_week", "day_sin", "day_cos", "is_weekend",
            "hour_of_day", "hour_sin", "hour_cos",
            "priority", "est_duration",
            "queue_length_at_arrival", "arrivals_last_1_hour", "avg_wait_last_1_hour",
            "actual_wait_minutes", "arrivals_next_2_hours", "is_surge_imminent",
        ]
        return df_final[columns]

    def generate_data(self, persist_to_db: bool = True) -> pd.DataFrame:
        df_visits = self.generate_arrivals()
        df_final = self.simulate_queue(df_visits)
        df_final = self.engineer_features(df_final)
        df_final = self.calculate_targets(df_final)
        df_final = self.finalize_dataset(df_final)

        if persist_to_db:
            self.persist_generated_data(df_final)
            self.logger.info(
                f"✅ Success! Saved {len(df_final)} rows to database table '{self.config.table_name}'"
            )

        display_columns = [
            "arrival_time", "hour_sin", "arrivals_last_1_hour", "queue_length_at_arrival", "is_surge_imminent"
        ]
        self.logger.info("\nSample Data (Features & Targets):")
        self.logger.info("\n%s", df_final[display_columns].head(10))
        return df_final


def main() -> None:
    generator = ClinicalAnnualVisitsGenerator()
    generator.generate_data(persist_to_db=True)


if __name__ == "__main__":
    main()