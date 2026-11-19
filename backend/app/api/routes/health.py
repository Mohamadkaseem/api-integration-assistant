"""Health check endpoint - lets the frontend (and later, monitoring tools)
confirm the backend is running."""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
    )
