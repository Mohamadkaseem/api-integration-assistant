"""Database connection.

- `engine` is the connection to the SQLite file.
- `create_db_and_tables()` creates the file and tables if they don't exist yet.
- `get_session()` gives each API request its own short-lived database session.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

settings = get_settings()

# Make sure the folder for the SQLite file exists (e.g. backend/data/).
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False lets FastAPI use the SQLite connection from different threads.
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    # Importing the models registers their tables with SQLModel before creating them.
    from app.models import analysis, api_doc, credential, design, handover, project, request_log  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
