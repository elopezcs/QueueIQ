from fastapi import FastAPI

from API.endpoints.routes import router as chatbot_router
try:
    from API.rag.routes import router as rag_router
except ModuleNotFoundError:
    rag_router = None
# from API.queuecontrol.routes import router as queuecontrol_router
# from API.simulator.routes import router as simulator_router


def register_routers(app: FastAPI) -> None:
    app.include_router(chatbot_router)
    if rag_router is not None:
        app.include_router(rag_router)
    # app.include_router(queuecontrol_router)
    # app.include_router(simulator_router)
