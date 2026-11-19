"""Entry point of the backend application.

Run it with:  uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.api.routes import health, projects
from app.core.config import get_settings
from app.db import create_db_and_tables, engine
from app.seed import seed_starter_projects

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Runs once when the server starts: make sure the database is ready.
    create_db_and_tables()
    with Session(engine) as session:
        seed_starter_projects(session)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Backend API for My API Integration Assistant",
    lifespan=lifespan,
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
app.include_router(projects.router, prefix="/api")
