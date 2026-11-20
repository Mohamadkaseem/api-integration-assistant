"""Entry point of the backend application.

Run it with:  uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.ai.provider import AIError
from app.api.routes import analysis, docs, health, projects, requests
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
    # One clear line in the terminal so you can see whether Claude is connected (never prints the key).
    logging.getLogger("uvicorn.error").info(
        "Claude API key: %s (model %s)", "found" if settings.ai_configured else "NOT FOUND - add ANTHROPIC_API_KEY to backend/.env", settings.ai_model
    )
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


@app.exception_handler(AIError)
async def handle_ai_error(_request: Request, exc: AIError) -> JSONResponse:
    # Turn AI problems into a clear message the frontend can show.
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# All our endpoints live under /api so they never clash with anything else.
app.include_router(health.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(docs.router, prefix="/api")
app.include_router(requests.router, prefix="/api")
