import importlib
import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

def _ensure_legacy_app_alias() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    backend_root = repo_root / "Chatbot" / "backend"
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)

    app_module = sys.modules.get("app")
    if app_module is None or not hasattr(app_module, "__path__"):
        sys.modules["app"] = importlib.import_module("Chatbot.backend.app")


_ensure_legacy_app_alias()
logger = logging.getLogger("queueiq.api")



def create_app() -> FastAPI:
    from API.router_registry import register_routers
    from Chatbot.backend.app.core.logging import configure_logging
    from Chatbot.backend.app.core.settings import settings
    from Chatbot.backend.app.storage.db import init_db

    configure_logging()
    logger.info("Creating QueueIQ FastAPI application")

    app = FastAPI(
        title="QueueIQ API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_db()
    logger.info("Primary application database initialized")
    register_routers(app)
    logger.info("API routers registered")
    return app


app = create_app()
