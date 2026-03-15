# QueueIQ

QueueIQ is a unified workspace with two product modules:
- `Chatbot/` for pre-arrival intake, appointment readiness, and admin review
- `QueueControl/` for live queue simulation, monitoring, and queue APIs

The repo root is the common entry point for the project.

## Prerequisites

Install these before setting up the project on a new machine:
- Git
- Python 3.10 or newer
- Node.js 18 or newer with `npm`

Verify your tools:

```powershell
git --version
python --version
npm --version
```

If `python` is not available on macOS or Linux, use `python3` in the commands below.

## Clone The Repository

```bash
git clone <your-repository-url>
cd queueIQ_Project1
```

## One Shared Python Environment

Use one root virtual environment for the whole workspace.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS or Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

Frontend dependencies still live in `Chatbot/frontend`.

Windows PowerShell:

```powershell
cd Chatbot\frontend
npm install
cd ..\..
```

macOS or Linux:

```bash
cd Chatbot/frontend
npm install
cd ../..
```

The repository now uses only the root `.venv`. Do not recreate module-level virtual environments.

## Optional Environment Setup

The Chatbot backend works without an API key by falling back to stub mode.

If you want live OpenAI responses, set `OPENAI_API_KEY` before starting the app.

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

macOS or Linux:

```bash
export OPENAI_API_KEY="your_api_key_here"
```

## Single Command Launcher

From the repo root, use the shared environment explicitly.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe app.py
```

macOS or Linux:

```bash
./.venv/bin/python app.py
```

This single launcher starts:
- Chatbot backend on `http://127.0.0.1:8000/docs`
- Chatbot frontend on `http://127.0.0.1:5173`
- QueueControl simulator in the background
- QueueControl backend on `http://127.0.0.1:8001/docs`
- QueueControl dashboard on `http://127.0.0.1:8501`

Keep that terminal open. Press `Ctrl+C` there to stop every process started by the launcher.

## Landing Page Only

If you only want the shared landing page and service-status view:

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS or Linux:

```bash
./.venv/bin/python -m streamlit run app.py
```

## Manual Module Runs

### Chatbot

Windows PowerShell:

```powershell
cd Chatbot\backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd Chatbot\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

macOS or Linux:

```bash
cd Chatbot/backend
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd Chatbot/frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### QueueControl

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe QueueControl\queue-simulation\backend-queue-simulation.py
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir QueueControl\backend
```

```powershell
.\.venv\Scripts\python.exe -m streamlit run QueueControl\queue-simulation\frontend-dashboard.py --server.address 127.0.0.1 --server.port 8501
```

macOS or Linux:

```bash
./.venv/bin/python QueueControl/queue-simulation/backend-queue-simulation.py
```

```bash
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir QueueControl/backend
```

```bash
./.venv/bin/python -m streamlit run QueueControl/queue-simulation/frontend-dashboard.py --server.address 127.0.0.1 --server.port 8501
```

## First-Run Checks

After startup, confirm these URLs load:
- Chatbot frontend: `http://127.0.0.1:5173`
- Chatbot backend docs: `http://127.0.0.1:8000/docs`
- QueueControl backend docs: `http://127.0.0.1:8001/docs`
- QueueControl dashboard: `http://127.0.0.1:8501`

## Notes

- The launcher skips services that are already reachable on their expected ports.
- If a port is busy but the expected app is not responding there, free that port first and rerun `app.py`.
- Chatbot CORS now allows both `http://localhost:5173` and `http://127.0.0.1:5173`.
- `Chatbot/frontend/node_modules` must exist for the launcher to start the frontend.
- `QueueControl/models/queueiq_xgb_model.joblib` must exist for the queue simulator to start.

