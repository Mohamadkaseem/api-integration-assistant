"""Shapes of a design's steps and field mappings (stored as JSON)."""

from typing import Literal

from pydantic import BaseModel, Field

Action = Literal["read", "search", "create", "update", "upsert", "delete", "send", "wait", "decide", "notify", "log", "other"]


class DesignStep(BaseModel):
    order: int
    app: str = Field(default="", max_length=100)
    action: Action = "other"
    description: str = Field(default="", max_length=2000)
    condition: str = Field(default="", max_length=1000)     # "only if the account exists"
    waits_for: str = Field(default="", max_length=1000)     # "signatory has signed"
    endpoint_id: int | None = None
    endpoint_label: str = ""                                # "PUT /crm/v3/Accounts/{id}" (filled by the server)
    match_status: Literal["unmatched", "matched", "manual", "no_endpoint"] = "unmatched"
    match_note: str = Field(default="", max_length=2000)    # why this endpoint / why none


class Mapping(BaseModel):
    source_app: str = Field(default="", max_length=100)
    source_field: str = Field(default="", max_length=300)
    target_app: str = Field(default="", max_length=100)
    target_field: str = Field(default="", max_length=300)
    transform: str = Field(default="", max_length=1000)     # "format as yyyy-MM-dd", "map picklist: Hot -> High"
    required: bool = False
    issue: Literal["none", "type", "date", "picklist", "nested", "required", "unknown"] = "none"
    notes: str = Field(default="", max_length=2000)
    evidence: Literal["documented", "assumed", "manual"] = "manual"
