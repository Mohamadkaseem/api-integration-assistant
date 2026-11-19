"""API Doc Analyzer endpoints.

  POST   /api/docs/import                     import from a file, pasted text or a URL
  GET    /api/docs?project_id=...             list imported documents
  GET    /api/docs/{id}                       one document with all its endpoints
  DELETE /api/docs/{id}                       delete a document and its endpoints
  DELETE /api/docs/{id}/endpoints/{eid}       remove one endpoint (e.g. a wrong unverified one)
"""

import json
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.deps import get_ai_provider_factory
from app.ai.provider import AIProvider
from app.db import get_session
from app.docs.importer import import_documentation
from app.docs.openapi_parser import SpecError
from app.docs.text_extract import ExtractError
from app.docs.types import AuthScheme, Parameter, ResponseInfo
from app.models.api_doc import ApiDocument, ApiEndpoint
from app.models.project import Project
from app.security.url_fetch import FetchError, UnsafeURLError, fetch_document

router = APIRouter(prefix="/docs", tags=["api docs"])

MAX_UPLOAD_BYTES = 30 * 1024 * 1024
MAX_TEXT_CHARS = 2_000_000


# ---------- Response shapes ----------


class EndpointOut(BaseModel):
    id: int
    method: str
    path: str
    summary: str
    description: str
    auth: str
    parameters: list[Parameter]
    request_body: str
    responses: list[ResponseInfo]
    verification: str
    evidence: str


class DocumentSummary(BaseModel):
    id: int
    project_id: int | None
    app_name: str
    title: str
    source_type: str
    source_ref: str
    created_at: datetime
    endpoint_count: int
    counts: dict[str, int]  # endpoints per verification level


class DocumentDetail(DocumentSummary):
    version: str
    base_urls: list[str]
    auth_schemes: list[AuthScheme]
    warnings: list[str]
    endpoints: list[EndpointOut]


def _endpoints(session: Session, document_id: int) -> list[ApiEndpoint]:
    return list(session.exec(select(ApiEndpoint).where(ApiEndpoint.document_id == document_id).order_by(ApiEndpoint.id)).all())


def _summary(doc: ApiDocument, endpoints: list[ApiEndpoint]) -> dict:
    counts = {"spec": 0, "quoted": 0, "unverified": 0}
    for e in endpoints:
        counts[e.verification] = counts.get(e.verification, 0) + 1
    return dict(
        id=doc.id, project_id=doc.project_id, app_name=doc.app_name, title=doc.title, source_type=doc.source_type,
        source_ref=doc.source_ref, created_at=doc.created_at, endpoint_count=len(endpoints), counts=counts,
    )


def _detail(session: Session, doc: ApiDocument) -> DocumentDetail:
    endpoints = _endpoints(session, doc.id)
    return DocumentDetail(
        **_summary(doc, endpoints),
        version=doc.version,
        base_urls=json.loads(doc.base_urls_json),
        auth_schemes=json.loads(doc.auth_schemes_json),
        warnings=json.loads(doc.warnings_json),
        endpoints=[
            EndpointOut(
                id=e.id, method=e.method, path=e.path, summary=e.summary, description=e.description, auth=e.auth,
                parameters=json.loads(e.parameters_json), request_body=e.request_body,
                responses=json.loads(e.responses_json), verification=e.verification, evidence=e.evidence,
            )
            for e in endpoints
        ],
    )


def _get_doc_or_404(session: Session, document_id: int) -> ApiDocument:
    doc = session.get(ApiDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    return doc


# ---------- Routes ----------


@router.post("/import", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def import_doc(
    app_name: str = Form(min_length=1, max_length=100),
    project_id: int | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    text: str | None = Form(default=None),
    url: str | None = Form(default=None, max_length=2000),
    session: Session = Depends(get_session),
    ai_provider: Callable[[], AIProvider] = Depends(get_ai_provider_factory),
) -> DocumentDetail:
    sources = [s for s in (file, (text or "").strip() or None, (url or "").strip() or None) if s is not None]
    if len(sources) != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one source: a file, pasted text, or a URL.")
    if project_id is not None and session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    filename, content_type = "", ""
    try:
        if file is not None:
            data = file.file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="The file is larger than 30 MB.")
            filename, content_type = file.filename or "upload", file.content_type or ""
            source_ref = filename
        elif text and text.strip():
            if len(text) > MAX_TEXT_CHARS:
                raise HTTPException(status_code=413, detail="The pasted text is too long (over 2 million characters).")
            data, source_ref = text.encode("utf-8"), "pasted text"
        else:
            fetched = fetch_document(url.strip())
            data, content_type, source_ref = fetched.content, fetched.content_type, fetched.url
            filename = fetched.url.rsplit("/", 1)[-1]

        parsed, source_type = import_documentation(
            data, filename=filename, content_type=content_type, get_provider=ai_provider, source_label=source_ref,
        )
    except (UnsafeURLError, FetchError, ExtractError, SpecError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc = ApiDocument(
        project_id=project_id, app_name=app_name.strip(), title=parsed.title, source_type=source_type,
        source_ref=source_ref, version=parsed.version,
        base_urls_json=json.dumps(parsed.base_urls), auth_schemes_json=json.dumps([a.model_dump() for a in parsed.auth_schemes]),
        warnings_json=json.dumps(parsed.warnings),
    )
    session.add(doc)
    session.flush()  # gives doc an id
    for ep in parsed.endpoints:
        session.add(
            ApiEndpoint(
                document_id=doc.id, method=ep.method, path=ep.path, summary=ep.summary, description=ep.description,
                auth=ep.auth, parameters_json=json.dumps([p.model_dump() for p in ep.parameters]),
                request_body=ep.request_body, responses_json=json.dumps([r.model_dump() for r in ep.responses]),
                verification=ep.verification, evidence=ep.evidence,
            )
        )
    session.commit()
    session.refresh(doc)
    return _detail(session, doc)


@router.get("", response_model=list[DocumentSummary])
def list_docs(project_id: int | None = None, session: Session = Depends(get_session)) -> list[DocumentSummary]:
    query = select(ApiDocument).order_by(ApiDocument.id.desc())
    if project_id is not None:
        query = query.where(ApiDocument.project_id == project_id)
    return [DocumentSummary(**_summary(d, _endpoints(session, d.id))) for d in session.exec(query).all()]


@router.get("/{document_id}", response_model=DocumentDetail)
def get_doc(document_id: int, session: Session = Depends(get_session)) -> DocumentDetail:
    return _detail(session, _get_doc_or_404(session, document_id))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doc(document_id: int, session: Session = Depends(get_session)) -> None:
    doc = _get_doc_or_404(session, document_id)
    for e in _endpoints(session, document_id):
        session.delete(e)
    session.delete(doc)
    session.commit()


@router.delete("/{document_id}/endpoints/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(document_id: int, endpoint_id: int, session: Session = Depends(get_session)) -> None:
    endpoint = session.get(ApiEndpoint, endpoint_id)
    if endpoint is None or endpoint.document_id != document_id:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    session.delete(endpoint)
    session.commit()
