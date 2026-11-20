"""Request Builder API.

  POST   /api/requests/send               send a test request (writes need confirm_write=true)
  GET    /api/requests/history            recent requests (optionally ?project_id=)
  GET    /api/requests/history/{id}       one request with its response
  DELETE /api/requests/history/{id}       remove it from history
  GET    /api/requests/stats              counts for the dashboard
"""

import json
from datetime import datetime

import httpx2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.db import get_session
from app.http_runner.redact import is_secret_name, redact_body, redact_headers, redact_pairs, redact_url
from app.http_runner.runner import WRITE_METHODS, OutgoingRequest, RunResult, build_url, send_request
from app.credentials import oauth
from app.credentials import service as cred_service
from app.models.credential import Credential
from app.models.project import Project
from app.security.crypto import CredentialDecryptError
from app.models.request_log import RequestLog
from app.http_runner.deps import get_resolver, get_transport

router = APIRouter(prefix="/requests", tags=["request builder"])

HISTORY_BODY_LIMIT = 100_000


class SendRequest(BaseModel):
    request: OutgoingRequest
    confirm_write: bool = False
    project_id: int | None = None
    endpoint_id: int | None = None
    credential_id: int | None = None  # use a saved credential instead of typing auth details


class SendResponse(RunResult):
    history_id: int


class HistoryItem(BaseModel):
    id: int
    project_id: int | None
    endpoint_id: int | None
    method: str
    url: str
    status_code: int | None
    elapsed_ms: int
    error_kind: str
    created_at: datetime


class HistoryDetail(HistoryItem):
    request: dict
    response_headers: dict[str, str]
    response_body: str
    size_bytes: int
    error_message: str


class Stats(BaseModel):
    total: int
    successful: int  # 2xx / 3xx
    failed: int      # 4xx / 5xx / no response


def _known_secrets(req: OutgoingRequest) -> list[str]:
    """Every secret value typed for this request, so it can be blanked wherever it appears."""
    a = req.auth
    values = [a.token, a.password, a.key_value]
    values += [kv.value for kv in (*req.headers, *req.params, *req.form) if is_secret_name(kv.name)]
    # The bare token inside "Zoho-oauthtoken xyz" / "Bearer xyz" header values
    values += [kv.value.split(" ", 1)[-1] for kv in req.headers if is_secret_name(kv.name) and " " in kv.value]
    return [v for v in values if v]


def _redacted_request(req: OutgoingRequest, extra_secrets: list[str] | None = None, credential_id: int | None = None) -> dict:
    """What we save: everything needed to resend, minus secrets."""
    secrets = _known_secrets(req) + (extra_secrets or [])
    return {
        "credential_id": credential_id,
        "method": req.method,
        "url": redact_url(req.url),
        "params": redact_pairs([p.model_dump() for p in req.params]),
        "headers": redact_pairs([h.model_dump() for h in req.headers]),
        "body_type": req.body_type,
        "body": redact_body(req.body[:HISTORY_BODY_LIMIT], secrets),
        "form": redact_pairs([f.model_dump() for f in req.form]),
        # Only the auth *type* and non-secret settings are kept.
        "auth": {
            "type": req.auth.type,
            "username": req.auth.username,
            "key_name": req.auth.key_name,
            "key_in": req.auth.key_in,
            "token_prefix": req.auth.token_prefix,
        },
    }


@router.post("/send", response_model=SendResponse)
def send(
    data: SendRequest,
    session: Session = Depends(get_session),
    transport: httpx2.BaseTransport | None = Depends(get_transport),
    resolve=Depends(get_resolver),
) -> SendResponse:
    req = data.request
    if req.method in WRITE_METHODS and not data.confirm_write:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{req.method} requests can create, change or delete data. Confirm before sending.",
        )
    if data.project_id is not None and session.get(Project, data.project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {data.project_id} not found")

    credential, extra_secrets = None, []
    if data.credential_id is not None:
        credential = session.get(Credential, data.credential_id)
        if credential is None:
            raise HTTPException(status_code=404, detail=f"Credential {data.credential_id} not found")
        try:
            auth, extra_secrets = cred_service.auth_for(session, credential, transport, resolve)
        except (oauth.OAuthError, CredentialDecryptError) as exc:
            raise HTTPException(status_code=400, detail=f"Credential '{credential.name}': {getattr(exc, 'message', str(exc))}") from exc
        req = req.model_copy(update={"auth": auth})

    allow_private = get_settings().allow_private_network_requests
    result = send_request(req, allow_private=allow_private, resolve=resolve, transport=transport)

    # An OAuth access token can be revoked or expire early: refresh once and retry.
    # (A 401 means the server did not process the request, so retrying is safe.)
    if result.status_code == 401 and credential is not None and credential.type == "oauth2":
        try:
            cred_service.refresh_now(session, credential, transport, resolve)
            auth, extra_secrets = cred_service.auth_for(session, credential, transport, resolve)
            req = req.model_copy(update={"auth": auth})
            result = send_request(req, allow_private=allow_private, resolve=resolve, transport=transport)
        except oauth.OAuthError:
            pass  # keep the original 401 answer; the credential now shows the error

    log = RequestLog(
        project_id=data.project_id,
        endpoint_id=data.endpoint_id,
        method=req.method,
        url=redact_url(build_url(req)),
        request_json=json.dumps(_redacted_request(req, extra_secrets, data.credential_id)),
        status_code=result.status_code,
        elapsed_ms=result.elapsed_ms,
        size_bytes=result.size_bytes,
        response_headers_json=json.dumps(redact_headers(result.headers)),
        response_body=redact_body(result.body[:HISTORY_BODY_LIMIT], _known_secrets(req) + extra_secrets),
        error_kind=result.error_kind,
        error_message=result.error_message,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return SendResponse(**result.model_dump(), history_id=log.id)


def _item(log: RequestLog) -> dict:
    return dict(
        id=log.id, project_id=log.project_id, endpoint_id=log.endpoint_id, method=log.method, url=log.url,
        status_code=log.status_code, elapsed_ms=log.elapsed_ms, error_kind=log.error_kind, created_at=log.created_at,
    )


@router.get("/history", response_model=list[HistoryItem])
def history(
    project_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[HistoryItem]:
    query = select(RequestLog).order_by(RequestLog.id.desc()).limit(limit)
    if project_id is not None:
        query = query.where(RequestLog.project_id == project_id)
    return [HistoryItem(**_item(log)) for log in session.exec(query).all()]


@router.get("/history/{log_id}", response_model=HistoryDetail)
def history_detail(log_id: int, session: Session = Depends(get_session)) -> HistoryDetail:
    log = session.get(RequestLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Request not found in history")
    return HistoryDetail(
        **_item(log),
        request=json.loads(log.request_json),
        response_headers=json.loads(log.response_headers_json),
        response_body=log.response_body,
        size_bytes=log.size_bytes,
        error_message=log.error_message,
    )


@router.delete("/history/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(log_id: int, session: Session = Depends(get_session)) -> None:
    log = session.get(RequestLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Request not found in history")
    session.delete(log)
    session.commit()


@router.get("/stats", response_model=Stats)
def stats(session: Session = Depends(get_session)) -> Stats:
    total = session.exec(select(func.count()).select_from(RequestLog)).one()
    successful = session.exec(
        select(func.count()).select_from(RequestLog).where(RequestLog.status_code >= 200, RequestLog.status_code < 400)
    ).one()
    return Stats(total=total, successful=successful, failed=total - successful)
