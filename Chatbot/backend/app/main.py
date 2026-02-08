from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import configure_logging
from app.core.settings import settings
from app.storage.db import init_db

from app.api.routes_health import router as health_router
from app.api.routes_clinics import router as clinics_router
from app.api.routes_chat import router as chat_router


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="QueueIQ ArrivalSignal API",
        version="0.1.0",
    )

    # Simple dev CORS (tighten later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()

    app.include_router(health_router)
    app.include_router(clinics_router)
    app.include_router(chat_router)

    return app


app = create_app()
