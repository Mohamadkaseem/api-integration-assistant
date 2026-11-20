"""Error Troubleshooter API.

  POST /api/troubleshoot/explain   instant built-in explanation (no AI, free)
  POST /api/troubleshoot/ai        built-in explanation + Claude analysis with a corrected request

Input is either a saved request from history (history_id) or a pasted error.
Everything sent to the AI is redacted first - secrets never leave your computer.
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.ai.deps import get_ai_provider
from app.ai.provider import AIProvider
from app.ai.troubleshooter import TroubleshootAnalysis, analyze_error
from app.db import get_session
from app.http_runner.redact import redact_body, redact_headers, redact_pairs, redact_url
from app.models.api_doc import ApiEndpoint
from app.models.request_log import RequestLog
from app.troubleshoot.rules import Diagnosis, diagnose

router = APIRouter(prefix="/troubleshoot", tags=["troubleshooter"])


class PastedRequest(BaseModel):
    method: str = Field(default="", max_length=10)
    url: str = Field(default="", max_length=8000)
    headers: list[dict] = Field(default_factory=list, max_length=100)
    body_type: str = "none"
    body: str = Field(default="", max_length=200_000)


class TroubleshootIn(BaseModel):
    history_id: int | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    response_body: str = Field(default="", max_length=500_000)
    response_headers: dict[str, str] = Field(default_factory=dict)
    error_kind: str = ""
    error_message: str = ""
    request: PastedRequest | None = None
    endpoint_id: int | None = None


class Context(BaseModel):
    """Everything known about the failure - already redacted."""
    request: dict
    status_code: int | None
    response_body: str
    response_headers: dict[str, str]
    error_kind: str
    error_message: str
    endpoint_id: int | None
    credential_id: int | None


class ExplainOut(BaseModel):
    diagnosis: Diagnosis
    context: Context


class AIOut(ExplainOut):
    analysis: TroubleshootAnalysis


def _context(data: TroubleshootIn, session: Session) -> Context:
    if data.history_id is not None:
        log = session.get(RequestLog, data.history_id)
        if log is None:
            raise HTTPException(404, "Request not found in history")
        request = json.loads(log.request_json)  # saved already redacted
        return Context(
            request=request, status_code=log.status_code, response_body=log.response_body,
            response_headers=json.loads(log.response_headers_json), error_kind=log.error_kind,
            error_message=log.error_message, endpoint_id=log.endpoint_id, credential_id=request.get("credential_id"),
        )
    if data.status_code is None and not data.response_body.strip() and not data.error_kind:
        raise HTTPException(400, "Paste the error response (and the status code if you know it).")
    pasted = data.request or PastedRequest()
    request = {
        "method": pasted.method.upper(),
        "url": redact_url(pasted.url),
        "headers": redact_pairs([{"name": str(h.get("name", "")), "value": str(h.get("value", "")), "enabled": True} for h in pasted.headers]),
        "body_type": pasted.body_type,
        "body": redact_body(pasted.body),
    }
    return Context(
        request=request, status_code=data.status_code, response_body=redact_body(data.response_body),
        response_headers=redact_headers(data.response_headers), error_kind=data.error_kind,
        error_message=data.error_message, endpoint_id=data.endpoint_id, credential_id=None,
    )


def _diagnose(ctx: Context) -> Diagnosis:
    return diagnose(ctx.status_code, ctx.response_body, ctx.error_kind, ctx.error_message,
                    ctx.request.get("method", ""), {k.lower(): v for k, v in ctx.response_headers.items()})


def _documentation(session: Session, endpoint_id: int | None) -> dict | None:
    if endpoint_id is None:
        return None
    ep = session.get(ApiEndpoint, endpoint_id)
    if ep is None:
        return None
    return {
        "method": ep.method, "path": ep.path, "summary": ep.summary, "auth": ep.auth,
        "parameters": json.loads(ep.parameters_json), "request_body": ep.request_body[:15000],
        "responses": json.loads(ep.responses_json)[:10], "trust": ep.verification,
    }


@router.post("/explain", response_model=ExplainOut)
def explain(data: TroubleshootIn, session: Session = Depends(get_session)) -> ExplainOut:
    ctx = _context(data, session)
    return ExplainOut(diagnosis=_diagnose(ctx), context=ctx)


@router.post("/ai", response_model=AIOut)
def explain_with_ai(
    data: TroubleshootIn,
    session: Session = Depends(get_session),
    provider: AIProvider = Depends(get_ai_provider),
) -> AIOut:
    ctx = _context(data, session)
    diagnosis = _diagnose(ctx)
    analysis = analyze_error(
        provider, request=ctx.request, status_code=ctx.status_code, response_body=ctx.response_body,
        diagnosis=diagnosis.model_dump(), documentation=_documentation(session, ctx.endpoint_id),
    )
    return AIOut(diagnosis=diagnosis, context=ctx, analysis=analysis)
