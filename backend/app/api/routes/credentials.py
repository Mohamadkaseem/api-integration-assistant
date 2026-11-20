"""Saved credentials and OAuth connections.

  GET    /api/credentials                          list (never returns secrets)
  POST   /api/credentials                          create
  PATCH  /api/credentials/{id}                     update (blank secret fields = keep current value)
  DELETE /api/credentials/{id}                     delete
  POST   /api/credentials/{id}/oauth/exchange-code connect with a pasted authorization code (Zoho Self Client)
  GET    /api/credentials/{id}/oauth/authorize-url start "sign in with browser"
  POST   /api/credentials/{id}/oauth/refresh       get a new access token now (connection test)
  GET    /api/oauth/callback                       where the provider sends the browser back
"""

import secrets as pysecrets
import time
from datetime import datetime
from typing import Literal
from urllib.parse import quote

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import get_settings
from app.credentials import oauth, service
from app.db import get_session
from app.http_runner.deps import get_resolver, get_transport
from app.models.credential import Credential
from app.models.project import utc_now
from app.security.crypto import CredentialDecryptError

router = APIRouter(tags=["credentials"])

CredType = Literal["api_key", "bearer", "basic", "oauth2"]

# Pending browser sign-ins: state -> (credential id, expiry). Kept in memory; a restart just means "start again".
_PENDING_STATES: dict[str, tuple[int, float]] = {}
STATE_TTL = 15 * 60


class CredentialIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    app_name: str = Field(default="", max_length=100)
    type: CredType
    environment: Literal["sandbox", "production"] = "sandbox"
    notes: str = Field(default="", max_length=5000)
    # api_key
    key_name: str = Field(default="", max_length=200)
    key_in: Literal["header", "query"] = "header"
    key_value: str = Field(default="", max_length=20_000)
    # bearer / oauth2
    token: str = Field(default="", max_length=20_000)
    token_prefix: str = Field(default="", max_length=50)
    # basic
    username: str = Field(default="", max_length=500)
    password: str = Field(default="", max_length=10_000)
    # oauth2
    provider: Literal["zoho", "generic"] = "zoho"
    data_center: Literal["com", "eu", "in", "com.au", "jp", "ca"] = "com"
    client_id: str = Field(default="", max_length=500)
    client_secret: str = Field(default="", max_length=2000)
    scopes: str = Field(default="", max_length=4000)
    auth_url: str = Field(default="", max_length=2000)
    token_url: str = Field(default="", max_length=2000)
    client_auth_method: Literal["post", "basic"] = "post"


class CredentialUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    app_name: str | None = Field(default=None, max_length=100)
    environment: Literal["sandbox", "production"] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    key_name: str | None = None
    key_in: Literal["header", "query"] | None = None
    key_value: str | None = None
    token: str | None = None
    token_prefix: str | None = None
    username: str | None = None
    password: str | None = None
    data_center: Literal["com", "eu", "in", "com.au", "jp", "ca"] | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    client_auth_method: Literal["post", "basic"] | None = None


class CredentialOut(BaseModel):
    id: int
    name: str
    app_name: str
    type: str
    environment: str
    notes: str
    status: str
    last_error: str
    settings: dict          # non-secret settings
    secret_hint: str        # e.g. "…a1b2" so you can tell keys apart; never the full secret
    has_refresh_token: bool
    expires_at: float | None
    redirect_uri: str
    created_at: datetime
    updated_at: datetime


class CodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=4000)


SECRET_FIELDS = ("key_value", "token", "password", "client_secret")
OAUTH_PUBLIC = ("provider", "data_center", "scopes", "auth_url", "token_url", "client_auth_method", "token_prefix")


def _hint(value: str) -> str:
    return f"…{value[-4:]}" if len(value) >= 8 else ("set" if value else "")


def _out(cred: Credential) -> CredentialOut:
    public = service.public_of(cred)
    try:
        secret = service.secret_of(cred)
    except CredentialDecryptError as exc:
        secret, cred.status, cred.last_error = {}, "error", str(exc)
    main = secret.get("key_value") or secret.get("token") or secret.get("password") or secret.get("refresh_token") or ""
    settings = {k: v for k, v in public.items() if k != "expires_at"}
    if secret.get("client_id"):
        settings["client_id"] = secret["client_id"][:6] + "…" if len(secret["client_id"]) > 8 else secret["client_id"]
    return CredentialOut(
        id=cred.id, name=cred.name, app_name=cred.app_name, type=cred.type, environment=cred.environment,
        notes=cred.notes, status=cred.status, last_error=cred.last_error, settings=settings, secret_hint=_hint(main),
        has_refresh_token=bool(secret.get("refresh_token")), expires_at=public.get("expires_at"),
        redirect_uri=get_settings().oauth_redirect_uri, created_at=cred.created_at, updated_at=cred.updated_at,
    )


def _get(session: Session, cred_id: int) -> Credential:
    cred = session.get(Credential, cred_id)
    if cred is None:
        raise HTTPException(status_code=404, detail=f"Credential {cred_id} not found")
    return cred


def _split(data: CredentialIn) -> tuple[dict, dict]:
    """Separate non-secret settings (public) from secrets (encrypted)."""
    t = data.type
    if t == "api_key":
        if not data.key_name or not data.key_value:
            raise HTTPException(400, "An API key needs a name (e.g. X-API-Key) and a value.")
        return {"key_name": data.key_name, "key_in": data.key_in}, {"key_value": data.key_value}
    if t == "bearer":
        if not data.token:
            raise HTTPException(400, "Enter the token.")
        return {"token_prefix": data.token_prefix or "Bearer"}, {"token": data.token}
    if t == "basic":
        if not data.username:
            raise HTTPException(400, "Enter the username.")
        return {"username": data.username}, {"password": data.password}
    # oauth2
    if not data.client_id or not data.client_secret:
        raise HTTPException(400, "OAuth needs a Client ID and a Client Secret (from the app's API console).")
    if data.provider == "generic" and not data.token_url:
        raise HTTPException(400, "Enter the token URL of the OAuth provider.")
    public = {k: getattr(data, k) for k in OAUTH_PUBLIC}
    public["token_prefix"] = data.token_prefix or ("Zoho-oauthtoken" if data.provider == "zoho" else "Bearer")
    return public, {"client_id": data.client_id, "client_secret": data.client_secret}


def _oauth_failure(session: Session, cred: Credential, exc: oauth.OAuthError):
    service.mark_error(session, cred, exc.message)
    raise HTTPException(status_code=400, detail=exc.message) from exc


# ---------- CRUD ----------


@router.get("/credentials", response_model=list[CredentialOut])
def list_credentials(session: Session = Depends(get_session)) -> list[CredentialOut]:
    return [_out(c) for c in session.exec(select(Credential).order_by(Credential.name)).all()]


@router.post("/credentials", response_model=CredentialOut, status_code=status.HTTP_201_CREATED)
def create_credential(data: CredentialIn, session: Session = Depends(get_session)) -> CredentialOut:
    public, secret = _split(data)
    cred = Credential(
        name=data.name.strip(), app_name=data.app_name.strip(), type=data.type, environment=data.environment,
        notes=data.notes, status="needs_authorization" if data.type == "oauth2" else "ready",
    )
    service.save(session, cred, public, secret)
    return _out(cred)


@router.patch("/credentials/{cred_id}", response_model=CredentialOut)
def update_credential(cred_id: int, data: CredentialUpdate, session: Session = Depends(get_session)) -> CredentialOut:
    cred = _get(session, cred_id)
    public, secret = service.public_of(cred), service.secret_of(cred)
    changes = data.model_dump(exclude_unset=True)
    for field in ("name", "app_name", "environment", "notes"):
        if field in changes and changes[field] is not None:
            setattr(cred, field, changes[field].strip() if isinstance(changes[field], str) else changes[field])
    reconnect = False
    for field, value in changes.items():
        if field in ("name", "app_name", "environment", "notes") or value is None:
            continue
        if field in SECRET_FIELDS or field == "client_id":
            if value.strip():  # blank = keep the stored secret
                secret[field] = value
                reconnect = reconnect or field in ("client_id", "client_secret")
        else:
            public[field] = value
            reconnect = reconnect or field in ("data_center", "token_url", "scopes")
    if cred.type == "oauth2" and reconnect:
        # Different client / server / scopes: old tokens no longer apply.
        secret.pop("access_token", None)
        secret.pop("refresh_token", None)
        public.pop("expires_at", None)
        cred.status, cred.last_error = "needs_authorization", ""
    service.save(session, cred, public, secret)
    return _out(cred)


@router.delete("/credentials/{cred_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(cred_id: int, session: Session = Depends(get_session)) -> None:
    session.delete(_get(session, cred_id))
    session.commit()


# ---------- OAuth ----------


def _require_oauth(cred: Credential):
    if cred.type != "oauth2":
        raise HTTPException(400, "This credential is not an OAuth 2.0 connection.")


@router.post("/credentials/{cred_id}/oauth/exchange-code", response_model=CredentialOut)
def exchange_code(
    cred_id: int, data: CodeIn, session: Session = Depends(get_session),
    transport: httpx2.BaseTransport | None = Depends(get_transport), resolve=Depends(get_resolver),
) -> CredentialOut:
    cred = _get(session, cred_id)
    _require_oauth(cred)
    public = service.public_of(cred)
    # Zoho Self Client codes need no redirect_uri; other providers expect the registered one.
    redirect = None if public.get("provider") == "zoho" else get_settings().oauth_redirect_uri
    try:
        tokens = oauth.exchange_code(public, service.secret_of(cred), data.code, redirect, transport=transport, resolve=resolve)
    except oauth.OAuthError as exc:
        _oauth_failure(session, cred, exc)
    service.store_tokens(session, cred, tokens)
    return _out(cred)


class AuthorizeUrl(BaseModel):
    url: str
    redirect_uri: str


@router.get("/credentials/{cred_id}/oauth/authorize-url", response_model=AuthorizeUrl)
def authorize_url(cred_id: int, session: Session = Depends(get_session)) -> AuthorizeUrl:
    cred = _get(session, cred_id)
    _require_oauth(cred)
    public = service.public_of(cred)
    if public.get("provider") == "generic" and not public.get("auth_url"):
        raise HTTPException(400, "Enter the provider's authorization URL to use browser sign-in.")
    now = time.time()
    for key in [k for k, (_, exp) in _PENDING_STATES.items() if exp < now]:
        del _PENDING_STATES[key]
    state = pysecrets.token_urlsafe(24)  # random value that proves the callback belongs to this request
    _PENDING_STATES[state] = (cred.id, now + STATE_TTL)
    redirect = get_settings().oauth_redirect_uri
    return AuthorizeUrl(url=oauth.build_authorize_url(public, service.secret_of(cred)["client_id"], redirect, state), redirect_uri=redirect)


@router.post("/credentials/{cred_id}/oauth/refresh", response_model=CredentialOut)
def refresh_token(
    cred_id: int, session: Session = Depends(get_session),
    transport: httpx2.BaseTransport | None = Depends(get_transport), resolve=Depends(get_resolver),
) -> CredentialOut:
    cred = _get(session, cred_id)
    _require_oauth(cred)
    try:
        service.refresh_now(session, cred, transport, resolve)
    except oauth.OAuthError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    return _out(cred)


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(
    state: str = "", code: str = "", error: str = "", accounts_server: str = Query(default="", alias="accounts-server"),
    session: Session = Depends(get_session),
    transport: httpx2.BaseTransport | None = Depends(get_transport), resolve=Depends(get_resolver),
):
    frontend = get_settings().frontend_url.rstrip("/")

    def back(**params) -> RedirectResponse:
        query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return RedirectResponse(f"{frontend}/credentials?{query}", status_code=303)

    pending = _PENDING_STATES.pop(state, None)
    if pending is None or pending[1] < time.time():
        return back(oauth_error="This sign-in link expired or was already used. Click 'Sign in with browser' again.")
    cred = session.get(Credential, pending[0])
    if cred is None:
        return back(oauth_error="The credential was deleted.")
    if error:
        service.mark_error(session, cred, oauth.explain(error))
        return back(oauth_error=oauth.explain(error), id=cred.id)
    public = service.public_of(cred)
    # Zoho may send the user's real data centre back; accept it only if it is a known Zoho accounts server.
    if public.get("provider") == "zoho" and accounts_server:
        for dc, server in oauth.ZOHO_ACCOUNTS.items():
            if accounts_server.rstrip("/") == server:
                public["data_center"] = dc
    try:
        tokens = oauth.exchange_code(public, service.secret_of(cred), code, get_settings().oauth_redirect_uri,
                                     transport=transport, resolve=resolve)
    except oauth.OAuthError as exc:
        service.mark_error(session, cred, exc.message)
        return back(oauth_error=exc.message, id=cred.id)
    service.save(session, cred, public, service.secret_of(cred))
    service.store_tokens(session, cred, tokens)
    cred.updated_at = utc_now()
    return back(connected=cred.id)
