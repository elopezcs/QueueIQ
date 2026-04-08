from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ServiceEndpoint:
    name: str
    url: str
    description: str
    health_url: str | None = None


@dataclass(frozen=True)
class ProductModule:
    name: str
    tagline: str
    folder: str
    description: str
    highlights: Sequence[str]
    run_steps: Sequence[str]
    services: Sequence[ServiceEndpoint]


QUEUEIQ_MODULES: tuple[ProductModule, ...] = (
    ProductModule(
        name="ArrivalSignal Chatbot",
        tagline="Pre-arrival intake and appointment readiness",
        folder="Chatbot/",
        description=(
            "Collects intake details, guides walk-in patients, and returns operational "
            "results such as urgency band, visit category, and expected wait windows."
        ),
        highlights=(
            "FastAPI backend with Swagger docs",
            "React frontend for guided intake",
            "Patient demo login, appointments, and admin review filters",
        ),
        run_steps=(
            ".\\.venv\\Scripts\\python.exe -m uvicorn API.main:app --host 127.0.0.1 --port 8000",
            "cd Chatbot/frontend",
            "npm run dev -- --host 127.0.0.1 --port 5173",
        ),
        services=(
            ServiceEndpoint(
                name="Frontend",
                url="http://127.0.0.1:5173",
                description="Patient-facing intake experience",
            ),
            ServiceEndpoint(
                name="Backend API",
                url="http://127.0.0.1:8000/docs",
                description="FastAPI endpoints and Swagger",
                health_url="http://127.0.0.1:8000/health",
            ),
        ),
    ),
    ProductModule(
        name="QueueControl",
        tagline="Operational queue simulation and clinic monitoring",
        folder="QueueControl/",
        description=(
            "Simulates clinic queues, tracks demand patterns, and exposes live queue "
            "dashboards plus a FastAPI surface for queue data."
        ),
        highlights=(
            "Streamlit dashboard for live queue visibility",
            "Simulation engine backed by queue data and trained model artifacts",
            "Internal backend service for queue processing",
        ),
        run_steps=(
            ".\\.venv\\Scripts\\python.exe QueueControl\\queue-simulation\\backend-queue-simulation.py",
            ".\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --app-dir QueueControl\\backend",
            ".\\.venv\\Scripts\\python.exe -m streamlit run QueueControl\\queue-simulation\\queue_simulation.py --server.address 127.0.0.1 --server.port 8501",
        ),
        services=(
            ServiceEndpoint(
                name="Dashboard",
                url="http://127.0.0.1:8501",
                description="Live queue simulation dashboard",
            ),
        ),
    ),
)


COMMON_LIBRARY_NOTES: tuple[str, ...] = (
    "Use `.\\.venv\\Scripts\\python.exe app.py` from the repo root to start the full workspace.",
    "Use `streamlit run app.py` when you only want the shared landing page and service status view.",
    "Keep repo-wide ignores in the root `.gitignore` instead of app-specific duplicates.",
    "Treat the root package as the place for shared project metadata and launcher utilities.",
)

