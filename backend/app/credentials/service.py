"""Turns a saved credential into request authentication, refreshing OAuth tokens when needed."""

import json
import time

import httpx2
from sqlmodel import Session

from app.credentials import oauth
from app.http_runner.runner import AuthConfig
from app.models.credential import Credential
from app.models.project import utc_now
from app.security.crypto import decrypt_json, encrypt_json

REFRESH_MARGIN_SECONDS = 120  # renew a little before the token actually expires


def public_of(cred: Credential) -> dict:
    return json.loads(cred.public_json or "{}")


def secret_of(cred: Credential) -> dict:
    return decrypt_json(cred.secret_encrypted)


def save(session: Session, cred: Credential, public: dict, secret: dict) -> None:
    cred.public_json = json.dumps(public)
    cred.secret_encrypted = encrypt_json(secret)
    cred.updated_at = utc_now()
    session.add(cred)
    session.commit()
    session.refresh(cred)


def store_tokens(session: Session, cred: Credential, tokens: oauth.TokenResult) -> None:
    public, secret = public_of(cred), secret_of(cred)
    secret["access_token"] = tokens.access_token
    if tokens.refresh_token:
        secret["refresh_token"] = tokens.refresh_token
    public["expires_at"] = tokens.expires_at
    if tokens.api_domain:
        public["api_domain"] = tokens.api_domain
    if tokens.scope:
        public["granted_scope"] = tokens.scope
    cred.status, cred.last_error = "ready", ""
    save(session, cred, public, secret)


def mark_error(session: Session, cred: Credential, message: str) -> None:
    cred.status, cred.last_error, cred.updated_at = "error", message, utc_now()
    session.add(cred)
    session.commit()


def refresh_now(session: Session, cred: Credential, transport: httpx2.BaseTransport | None = None, resolve=None) -> None:
    kwargs = {"transport": transport}
    if resolve is not None:
        kwargs["resolve"] = resolve
    try:
        tokens = oauth.refresh(public_of(cred), secret_of(cred), **kwargs)
    except oauth.OAuthError as exc:
        mark_error(session, cred, exc.message)
        raise
    store_tokens(session, cred, tokens)


def auth_for(session: Session, cred: Credential, transport: httpx2.BaseTransport | None = None, resolve=None) -> tuple[AuthConfig, list[str]]:
    """Return (AuthConfig for the request, list of secret values for redaction)."""
    public, secret = public_of(cred), secret_of(cred)
    if cred.type == "api_key":
        auth = AuthConfig(type="api_key", key_name=public.get("key_name", ""), key_in=public.get("key_in", "header"),
                          key_value=secret.get("key_value", ""))
    elif cred.type == "bearer":
        auth = AuthConfig(type="bearer", token=secret.get("token", ""), token_prefix=public.get("token_prefix", "Bearer"))
    elif cred.type == "basic":
        auth = AuthConfig(type="basic", username=public.get("username", ""), password=secret.get("password", ""))
    elif cred.type == "oauth2":
        if not secret.get("refresh_token") and not secret.get("access_token"):
            raise oauth.OAuthError("not_connected", f"'{cred.name}' is not connected yet. Open Credentials and connect it.")
        if not secret.get("access_token") or float(public.get("expires_at") or 0) - REFRESH_MARGIN_SECONDS < time.time():
            refresh_now(session, cred, transport, resolve)
            public, secret = public_of(cred), secret_of(cred)
        auth = AuthConfig(type="bearer", token=secret["access_token"], token_prefix=public.get("token_prefix", "Bearer"))
    else:
        raise ValueError(f"Unknown credential type {cred.type}")
    known = [v for v in secret.values() if isinstance(v, str) and v]
    return auth, known
