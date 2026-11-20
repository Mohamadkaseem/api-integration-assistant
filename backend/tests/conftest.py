"""Shared test setup.

Every test gets a brand-new, empty in-memory database, so tests never touch
your real data/app.db file and never affect each other.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
from app.models import analysis, api_doc, credential, design, handover, project, request_log  # noqa: F401  (registers the tables)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(session):
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def temporary_encryption_key(monkeypatch):
    """Each test encrypts with a throw-away key, so no key file is ever written by tests."""
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from app.core.config import get_settings
    from app.security.crypto import get_fernet

    monkeypatch.setattr(get_settings(), "credentials_key", SecretStr(Fernet.generate_key().decode()))
    get_fernet.cache_clear()
    yield
    get_fernet.cache_clear()
