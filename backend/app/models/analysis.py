"""Saved requirement analyses. Every run is kept, so you can see how the analysis
changed as the client answered questions."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class AnalysisRecord(SQLModel, table=True):
    __tablename__ = "requirement_analyses"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)
    requirement: str            # the exact text that was analyzed
    clarifications_json: str    # the Q&A that was included, as JSON
    result_json: str            # the RequirementAnalysis, as JSON
    ai_provider: str
    ai_model: str
    created_at: datetime = Field(default_factory=utc_now)
