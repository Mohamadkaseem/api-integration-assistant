"""Optional AI additions to a project's handover document."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class HandoverNotes(SQLModel, table=True):
    __tablename__ = "handover_notes"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", unique=True, index=True)
    ai_summary: str = ""
    ai_test_cases_json: str = "[]"
    updated_at: datetime = Field(default_factory=utc_now)
