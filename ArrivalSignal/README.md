# QueueIQ ArrivalSignal

ArrivalSignal is the pre-arrival demand shaping module for QueueIQ (walk-in clinics):
- A user selects a clinic
- Chats with an intake assistant (up to ~10 turns)
- Receives operational outputs only:
  - urgency band (low/medium/high)
  - visit category (operational bucket)
  - queue risk (wait P50/P90) based on a mock snapshot + heuristic

Important:
- This is NOT a diagnostic system.
- No diagnosis, no treatment, no medication advice.
- If severe or emergency-like content is detected, the system returns safe escalation guidance.

---

## Prerequisites
- Python 3.10+ (recommended 3.11)
- Node 18+ (recommended 20)
- On Windows: PowerShell is fine.

---

## 1) Backend setup (FastAPI)

From repo root:

```bash
cd backend
python -m venv .venv
```

Activate venv:

**Windows PowerShell**
```powershell
. .venv\Scripts\Activate.ps1
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -U pip
pip install -e ".[dev]"
```

Create a `.env` in `backend/`:

```bash
# from backend/
cp ../.env.example .env
```

Edit `backend/.env` and set `OPENAI_API_KEY` if you want real LLM behavior. If you leave it blank, the app runs in **stub mode** with a scripted question flow.

Run the API:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open docs:
- http://127.0.0.1:8000/docs

Database notes:
- SQLite file is created in `backend/app.db` by default.
- To change the path, set `SQLITE_PATH` in `backend/.env`.

Clinic config:
- Edit `backend/app/config/clinics.yaml` to add clinics or change mock capacity.

---

## 2) Frontend setup (React + Vite)

In a new terminal, from repo root:

```bash
cd frontend
npm install
```

Optional: create `frontend/.env` (recommended if your backend is not on 127.0.0.1:8000):

```bash
echo VITE_API_BASE=http://127.0.0.1:8000 > .env
```

Run the frontend:

```bash
npm run dev
```

Open:
- http://localhost:5173

---

## 3) Quick smoke test flow
1. Start backend on 127.0.0.1:8000
2. Start frontend on localhost:5173
3. Select a clinic and click "Start intake"
4. Chat for a few turns, then click "Finish"
5. Confirm Results show urgency band, visit category, and wait P50/P90

---

## Tests

Backend unit + smoke integration tests:

```bash
cd backend
pytest
```

---

## Troubleshooting

**CORS error**
- Ensure frontend is at http://localhost:5173
- Backend allows that origin by default
- If you run frontend elsewhere, update `cors_allow_origins` in `backend/app/core/settings.py`

**OPENAI_API_KEY not set**
- This is fine. The system runs in stub mode.
- To enable LLM calls, set `OPENAI_API_KEY` in `backend/.env`.

**Windows venv activation blocked**
- In PowerShell, you may need:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

---

## TODOs for production hardening
- Auth, rate limiting, and abuse protections
- Better JSON output enforcement and repair for LLM outputs
- Controlled taxonomy for visit categories
- Observability: request ids, tracing, metrics
- Add GitHub Actions workflow for lint + tests

---

## OpenAI Responses API note

This scaffold uses the OpenAI SDK Responses API style:
- `client.responses.create(...)`
- `response.output_text`

See OpenAI migration guidance:
https://platform.openai.com/docs/guides/migrate-to-responses
