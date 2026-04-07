import importlib
import sys

from fastapi import APIRouter
from API.endpoints.routes_admin import router as admin_router
from API.endpoints.routes_appointments import router as appointments_router
from API.endpoints.routes_auth import router as auth_router
from API.endpoints.routes_chat import router as chat_router
from API.endpoints.routes_clinics import router as clinics_router
from API.endpoints.routes_health import router as health_router
from API.queuecontrol.routes import router as queuecontrol_router


app_module = sys.modules.get("app")
if app_module is None or not hasattr(app_module, "__path__"):
    sys.modules["app"] = importlib.import_module("Chatbot.backend.app")



router = APIRouter()
router.include_router(health_router)
router.include_router(clinics_router)
router.include_router(chat_router)
router.include_router(auth_router)
router.include_router(appointments_router)
router.include_router(admin_router)
router.include_router(queuecontrol_router)
