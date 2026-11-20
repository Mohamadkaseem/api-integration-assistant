"""History of requests sent from the Request Builder.

Secrets are masked before saving (headers like Authorization, API keys, tokens,
cookies). The response body is kept (first 100 KB) so you can review it later.
"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class RequestLog(SQLModel, table=True):
    __tablename__ = "request_logs"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(default=None, foreign_key="project.id", index=True)
    endpoint_id: int | None = Field(default=None)       # imported endpoint it started from, if any
    method: str
    url: str                                            # redacted
    request_json: str                                   # params/headers/body/auth type - redacted
    status_code: int | None = None
    elapsed_ms: int = 0
    size_bytes: int = 0
    response_headers_json: str = "{}"                   # redacted
    response_body: str = ""                             # first 100 KB
    error_kind: str = ""
    error_message: str = ""
    created_at: datetime = Field(default_factory=utc_now)
