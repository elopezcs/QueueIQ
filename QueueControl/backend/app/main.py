from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_health import router as health_router
from app.api.routes_queue import router as queue_router

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Health and readiness checks for the QueueControl backend.",
    },
    {
        "name": "queue-control",
        "description": "Queue snapshots, clinic status, and patient intake endpoints for QueueControl.",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="QueueIQ QueueControl API",
        version="0.1.0",
        description="Swagger-enabled API for QueueControl queue monitoring and patient intake.",
        openapi_tags=OPENAPI_TAGS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(queue_router)
    return app


app = create_app()
