# QueueIQ QueueControl

QueueControl handles rush-hour simulations, queue management, the live dashboard, and queue APIs.

## Preferred local run

Use the shared root `.venv` from the repository root. QueueControl-specific virtual environments are no longer part of the supported setup.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

That launcher starts:
- QueueControl simulator in the background
- QueueControl backend on `http://127.0.0.1:8001/docs`
- QueueControl dashboard on `http://127.0.0.1:8501`

## Running only QueueControl simulation

Simulator:

```powershell
.\.venv\Scripts\python.exe QueueControl\queue-simulation\queue_simulation.py
```

API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir QueueControl\backend
```

Historical Clinical Synthetic Data:
- Training the rush hour probability model relies on synthetic clinical historical data. To run only the synthetic data generation file, run below command:
```powershell
.\.venv\Scripts\python.exe QueueControl\synthetic-data-generation\clinical_annual_visits.py
```

## Notes
- Use the root `requirements.txt` as the shared dependency file for the full workspace.
- The simulator keeps the queue data clinic_queue in Postgresql local database  moving so the dashboard and queue API have live data to show.
