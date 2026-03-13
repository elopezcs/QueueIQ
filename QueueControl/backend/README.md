# QueueControl Backend API

This backend is isolated from `Chatbot` and runs only inside `QueueControl/.venv`.

## Run

From the repository root:

```bash
QueueControl\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir QueueControl\backend --port 8001
```

## Swagger

- Swagger UI: `http://127.0.0.1:8001/docs`
- OpenAPI JSON: `http://127.0.0.1:8001/openapi.json`

## Endpoints

- `GET /health`
- `GET /queue-control/clinics`
- `GET /queue-control/overview`
- `GET /queue-control/queues`
- `GET /queue-control/clinics/{clinic_id}/queue`
- `POST /queue-control/clinics/{clinic_id}/patients`
