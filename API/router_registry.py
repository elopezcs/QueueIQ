from fastapi import FastAPI

from API.endpoints.routes_admin import router as admin_router
from API.endpoints.routes_appointments import router as appointments_router
from API.endpoints.routes_auth import router as auth_router
from API.endpoints.routes_chat import router as chatbot_router
from API.endpoints.routes_clinics import router as clinics_router
from API.endpoints.routes_health import router as health_router
from API.endpoints.routes_traceability import router as traceability_router
from API.queuecontrol.routes import router as queuecontrol_router
from API.rag.routes import router as rag_router
# from API.simulator.routes import router as simulator_router


def register_routers(app: FastAPI) -> None:
    app.include_router(health_router)
    app.include_router(clinics_router)
    app.include_router(chatbot_router)
    app.include_router(auth_router)
    app.include_router(appointments_router)
    app.include_router(traceability_router)
    app.include_router(admin_router)
    app.include_router(queuecontrol_router)
    app.include_router(rag_router)
    # app.include_router(simulator_router)
