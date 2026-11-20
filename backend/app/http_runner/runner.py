"""Sends a test API request built in the Request Builder.

Safety rules:
  * Only http/https; private / local network addresses are refused unless
    ALLOW_PRIVATE_NETWORK_REQUESTS=true is set in backend/.env.
  * Redirects are NOT followed automatically - you see the 3xx answer and where it points.
  * 30 second timeout; at most 5 MB of the response is read.
  * Credentials are only used to build this one request. They are never stored.
"""

import base64
import json
import time
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx2
from pydantic import BaseModel, Field

from app.security.url_fetch import FetchError, UnsafeURLError, _resolve, check_url_is_public

TIMEOUT_SECONDS = 30.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
USER_AGENT = "MyAPIIntegrationAssistant/0.5"

Method = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class KeyValue(BaseModel):
    name: str = Field(max_length=500)
    value: str = Field(default="", max_length=20_000)
    enabled: bool = True


class AuthConfig(BaseModel):
    type: Literal["none", "bearer", "basic", "api_key"] = "none"
    token: str = Field(default="", max_length=20_000)       # bearer
    username: str = Field(default="", max_length=1_000)     # basic
    password: str = Field(default="", max_length=10_000)    # basic
    key_name: str = Field(default="", max_length=500)       # api_key
    key_value: str = Field(default="", max_length=20_000)   # api_key
    key_in: Literal["header", "query"] = "header"           # api_key
    token_prefix: str = Field(default="Bearer", max_length=50)  # e.g. "Zoho-oauthtoken" for Zoho APIs


class OutgoingRequest(BaseModel):
    method: Method
    url: str = Field(min_length=1, max_length=8_000)
    params: list[KeyValue] = Field(default_factory=list, max_length=200)
    headers: list[KeyValue] = Field(default_factory=list, max_length=200)
    body_type: Literal["none", "json", "text", "form"] = "none"
    body: str = Field(default="", max_length=5_000_000)
    form: list[KeyValue] = Field(default_factory=list, max_length=500)
    auth: AuthConfig = Field(default_factory=AuthConfig)


class RunResult(BaseModel):
    ok: bool                       # a response was received (any status)
    status_code: int | None = None
    reason: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    body_truncated: bool = False
    is_binary: bool = False
    content_type: str = ""
    size_bytes: int = 0
    elapsed_ms: int = 0
    final_url: str = ""
    error_kind: str = ""           # blocked / dns / timeout / connection / invalid
    error_message: str = ""


class RequestNotAllowed(ValueError):
    pass


def build_url(req: OutgoingRequest) -> str:
    """Add the enabled query parameters (and an API key in the query, if chosen) to the URL."""
    parts = urlsplit(req.url.strip())
    query = parse_qsl(parts.query, keep_blank_values=True)
    query += [(p.name, p.value) for p in req.params if p.enabled and p.name.strip()]
    if req.auth.type == "api_key" and req.auth.key_in == "query" and req.auth.key_name:
        query.append((req.auth.key_name, req.auth.key_value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def build_headers(req: OutgoingRequest) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    for h in req.headers:
        if h.enabled and h.name.strip():
            headers[h.name.strip()] = h.value
    auth = req.auth
    if auth.type == "bearer" and auth.token:
        headers["Authorization"] = f"{auth.token_prefix.strip() or 'Bearer'} {auth.token.strip()}"
    elif auth.type == "basic":
        raw = f"{auth.username}:{auth.password}".encode()
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode()
    elif auth.type == "api_key" and auth.key_in == "header" and auth.key_name:
        headers[auth.key_name.strip()] = auth.key_value
    return headers


def build_body(req: OutgoingRequest, headers: dict[str, str]) -> dict:
    """Return httpx2 keyword arguments for the body."""
    lower = {k.lower() for k in headers}
    if req.method in ("GET", "HEAD") or req.body_type == "none":
        return {}
    if req.body_type == "json":
        try:
            json.loads(req.body or "null")
        except json.JSONDecodeError as exc:
            raise RequestNotAllowed(f"The body is not valid JSON (line {exc.lineno}, column {exc.colno}): {exc.msg}.") from exc
        if "content-type" not in lower:
            headers["Content-Type"] = "application/json"
        return {"content": req.body.encode("utf-8")}
    if req.body_type == "form":
        return {"data": {f.name: f.value for f in req.form if f.enabled and f.name.strip()}}
    if "content-type" not in lower:
        headers["Content-Type"] = "text/plain; charset=utf-8"
    return {"content": req.body.encode("utf-8")}


def _looks_binary(content_type: str, data: bytes) -> bool:
    if any(t in content_type for t in ("json", "xml", "text", "javascript", "html", "yaml", "x-www-form-urlencoded")):
        return False
    return b"\x00" in data[:2048] or bool(content_type) and not content_type.startswith("text")


def send_request(
    req: OutgoingRequest,
    *,
    allow_private: bool = False,
    resolve=_resolve,
    transport: httpx2.BaseTransport | None = None,
) -> RunResult:
    url = build_url(req)
    if not allow_private:
        try:
            check_url_is_public(url, resolve)
        except UnsafeURLError as exc:
            return RunResult(ok=False, error_kind="blocked", error_message=str(exc))
        except FetchError as exc:
            return RunResult(ok=False, error_kind="dns", error_message=str(exc))
    elif urlsplit(url).scheme not in ("http", "https"):
        return RunResult(ok=False, error_kind="blocked", error_message="Only http:// and https:// URLs are allowed.")

    headers = build_headers(req)
    try:
        body_kwargs = build_body(req, headers)
    except RequestNotAllowed as exc:
        return RunResult(ok=False, error_kind="invalid", error_message=str(exc))

    started = time.perf_counter()
    try:
        with httpx2.Client(follow_redirects=False, timeout=TIMEOUT_SECONDS, transport=transport) as client:
            with client.stream(req.method, url, headers=headers, **body_kwargs) as response:
                chunks, size, truncated = [], 0, False
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        truncated = True
                        break
                    chunks.append(chunk)
                elapsed = int((time.perf_counter() - started) * 1000)
                data = b"".join(chunks)
                content_type = response.headers.get("content-type", "")
                binary = _looks_binary(content_type.lower(), data)
                text = "" if binary else data.decode(response.encoding or "utf-8", errors="replace")
                return RunResult(
                    ok=True,
                    status_code=response.status_code,
                    reason=response.reason_phrase,
                    headers=dict(response.headers),
                    body=text,
                    body_truncated=truncated,
                    is_binary=binary,
                    content_type=content_type,
                    size_bytes=size,
                    elapsed_ms=elapsed,
                    final_url=str(response.url),
                )
    except httpx2.TimeoutException:
        return RunResult(ok=False, error_kind="timeout", elapsed_ms=int((time.perf_counter() - started) * 1000),
                         error_message=f"No answer within {int(TIMEOUT_SECONDS)} seconds.")
    except httpx2.ConnectError as exc:
        return RunResult(ok=False, error_kind="connection", error_message=f"Could not connect to the server ({exc.__class__.__name__}). Check the URL and your internet connection.")
    except httpx2.HTTPError as exc:
        return RunResult(ok=False, error_kind="connection", error_message=f"Request failed: {exc.__class__.__name__}: {exc}")
    except ValueError as exc:  # malformed URL etc.
        return RunResult(ok=False, error_kind="invalid", error_message=f"Invalid request: {exc}")
