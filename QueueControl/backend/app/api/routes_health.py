from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check", description="Returns a simple status payload to confirm the QueueControl API is running.")
def health() -> dict[str, str]:
    return {"status": "ok"}
