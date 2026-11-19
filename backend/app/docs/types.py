"""The common shape every documentation source is converted into.

Whatever the input (OpenAPI, Postman, PDF, web page), the result is a
`ParsedDoc` with a list of `ParsedEndpoint`s, so the rest of the app only has
to understand one format.
"""

from typing import Literal

from pydantic import BaseModel, Field

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

# How much we trust an endpoint:
#  spec       - read by code from an OpenAPI/Postman file (no AI involved)
#  quoted     - found by AI, and its quote + path were found word-for-word in the document
#  unverified - found by AI, but the check failed: review before using
Verification = Literal["spec", "quoted", "unverified"]


class Parameter(BaseModel):
    name: str
    location: Literal["path", "query", "header", "cookie", "body", "form", "unknown"]
    required: bool = False
    type: str = ""
    description: str = ""


class ResponseInfo(BaseModel):
    status: str
    description: str = ""
    example: str = ""


class ParsedEndpoint(BaseModel):
    method: HttpMethod
    path: str
    summary: str = ""
    description: str = ""
    auth: str = ""
    parameters: list[Parameter] = Field(default_factory=list)
    request_body: str = ""  # example or schema, as readable JSON text
    responses: list[ResponseInfo] = Field(default_factory=list)
    verification: Verification = "spec"
    evidence: str = ""  # for AI-found endpoints: the quote from the document


class AuthScheme(BaseModel):
    name: str
    type: str  # apiKey, http bearer, http basic, oauth2, ...
    details: str = ""


class ParsedDoc(BaseModel):
    title: str = ""
    version: str = ""
    base_urls: list[str] = Field(default_factory=list)
    auth_schemes: list[AuthScheme] = Field(default_factory=list)
    endpoints: list[ParsedEndpoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def short(text: object, limit: int = 4000) -> str:
    """Keep stored text readable: very long descriptions/examples are cut with a marker."""
    value = str(text or "").strip()
    return value if len(value) <= limit else value[:limit] + " …[shortened]"
