# QueueIQ ArrivalSignal

ArrivalSignal is the pre-arrival demand shaping module for QueueIQ.

## Preferred local run

Use the shared root `.venv` from the repository root. Module-specific virtual environments are no longer part of the supported setup.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd Chatbot\frontend
npm install
cd ..\..
.\.venv\Scripts\python.exe app.py
```

That launcher starts both:
- Chatbot backend on `http://127.0.0.1:8000/docs`
- Chatbot frontend on `http://127.0.0.1:5173`

## Manual Chatbot-only run

Backend:

```powershell
cd Chatbot\backend
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd Chatbot\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Notes

- The backend runs in stub mode if `OPENAI_API_KEY` is not set.
- The backend allows both `http://localhost:5173` and `http://127.0.0.1:5173` for local frontend access.
- Use the root `requirements.txt` as the shared dependency file for the full workspace.
