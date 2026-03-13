from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_appointments import router as appointments_router
from app.api.routes_auth import router as auth_router
from app.api.routes_chat import router as chat_router
from app.api.routes_clinics import router as clinics_router
from app.api.routes_health import router as health_router
from app.core.logging import configure_logging
from app.core.settings import settings
from app.storage.db import init_db


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title='QueueIQ Chatbot API',
        version='0.2.0',
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    init_db()

    app.include_router(health_router)
    app.include_router(clinics_router)
    app.include_router(chat_router)
    app.include_router(auth_router)
    app.include_router(appointments_router)
    app.include_router(admin_router)

    return app


app = create_app()
