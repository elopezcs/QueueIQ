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

## Manual QueueControl-only run

Simulator:

```powershell
.\.venv\Scripts\python.exe QueueControl\queue-simulation\backend-queue-simulation.py
```

API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir QueueControl\backend
```

Dashboard:

```powershell
.\.venv\Scripts\python.exe -m streamlit run QueueControl\queue-simulation\frontend-dashboard.py --server.address 127.0.0.1 --server.port 8501
```

## Notes

- Use the root `requirements.txt` as the shared dependency file for the full workspace.
- The simulator keeps `QueueControl/clinic_queue.csv` moving so the dashboard and queue API have live data to show.
