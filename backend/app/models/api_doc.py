"""Imported API documentation and the endpoints found in it."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class ApiDocument(SQLModel, table=True):
    __tablename__ = "api_documents"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, foreign_key="project.id", index=True)
    app_name: str = Field(index=True)       # e.g. "Zoho Sign"
    title: str = ""                         # title found in the document
    source_type: str                        # openapi / postman / pdf / html / text
    source_ref: str = ""                    # file name or URL
    version: str = ""
    base_urls_json: str = "[]"
    auth_schemes_json: str = "[]"
    warnings_json: str = "[]"
    created_at: datetime = Field(default_factory=utc_now)


class ApiEndpoint(SQLModel, table=True):
    __tablename__ = "api_endpoints"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="api_documents.id", index=True)
    method: str
    path: str
    summary: str = ""
    description: str = ""
    auth: str = ""
    parameters_json: str = "[]"
    request_body: str = ""
    responses_json: str = "[]"
    verification: str = "spec"              # spec / quoted / unverified
    evidence: str = ""
