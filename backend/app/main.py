"""Entry point of the backend application.

Run it with:  uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Backend API for My API Integration Assistant",
)

# CORS: browsers block a website from calling a different server unless that
# server explicitly allows it. We only allow our own frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# All our endpoints live under /api so they never clash with anything else.
app.include_router(health.router, prefix="/api")
