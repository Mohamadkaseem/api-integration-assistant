"""Saved credentials. Secrets live only in `secret_encrypted` (encrypted with Fernet)."""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.project import utc_now


class Credential(SQLModel, table=True):
    __tablename__ = "credentials"

    id: int | None = Field(default=None, primary_key=True)
    name: str                                  # e.g. "Zoho CRM - sandbox"
    app_name: str = ""
    type: str                                  # api_key / bearer / basic / oauth2
    environment: str = "sandbox"               # sandbox / production (a label, to avoid mistakes)
    notes: str = ""
    public_json: str = "{}"                    # NON-secret settings (key name, prefix, OAuth URLs, scopes, expiry...)
    secret_encrypted: str = ""                 # encrypted JSON: tokens, passwords, client secret, refresh token
    status: str = "ready"                      # ready / needs_authorization / error
    last_error: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
