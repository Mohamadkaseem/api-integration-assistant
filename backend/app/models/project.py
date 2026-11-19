"""The "Integration Project" model.

One class describes the database table (`Project`). The other classes describe
what the API accepts and returns, so users can't set fields like `id` themselves.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectStatus(str, Enum):
    planning = "planning"
    in_progress = "in_progress"
    testing = "testing"
    completed = "completed"
    on_hold = "on_hold"


class ProjectBase(SQLModel):
    """Fields shared by create, read and the table."""

    name: str = Field(min_length=1, max_length=200)
    source_app: str = Field(default="", max_length=100)
    target_app: str = Field(default="", max_length=100)
    requirement: str = Field(default="", max_length=20_000)
    status: ProjectStatus = ProjectStatus.planning
    notes: str = Field(default="", max_length=20_000)


class Project(ProjectBase, table=True):
    """The database table."""

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProjectCreate(ProjectBase):
    """What the API accepts when creating a project."""


class ProjectUpdate(SQLModel):
    """What the API accepts when editing: every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    source_app: str | None = Field(default=None, max_length=100)
    target_app: str | None = Field(default=None, max_length=100)
    requirement: str | None = Field(default=None, max_length=20_000)
    status: ProjectStatus | None = None
    notes: str | None = Field(default=None, max_length=20_000)


class ProjectRead(ProjectBase):
    """What the API returns."""

    id: int
    created_at: datetime
    updated_at: datetime
