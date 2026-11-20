"""One integration design per project: steps (with chosen endpoints) and field mappings."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class IntegrationDesign(SQLModel, table=True):
    __tablename__ = "integration_designs"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", unique=True, index=True)
    analysis_id: int | None = None          # requirement analysis the steps came from
    trigger: str = ""                       # e.g. "New company created in HubSpot"
    doc_ids_json: str = "[]"                # imported docs whose endpoints may be used
    steps_json: str = "[]"
    mappings_json: str = "[]"
    missing_docs_json: str = "[]"           # documentation the AI said is missing
    updated_at: datetime = Field(default_factory=utc_now)
