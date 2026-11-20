"""Integration design per project.

  GET  /api/projects/{id}/design                    design + diagram + endpoints available to choose from
  PUT  /api/projects/{id}/design                    save manual edits (steps, endpoints, mappings, docs)
  POST /api/projects/{id}/design/from-analysis      steps from the latest requirement analysis (no AI)
  POST /api/projects/{id}/design/match-endpoints    Claude picks endpoints - only from your imported docs
  POST /api/projects/{id}/design/suggest-mappings   Claude proposes field mappings - checked against docs
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.ai.deps import get_ai_provider
from app.ai.designer import match_endpoints, suggest_mappings
from app.ai.provider import AIProvider
from app.ai.requirement_analyzer import RequirementAnalysis
from app.db import get_session
from app.design import service
from app.design.mermaid import build_mermaid
from app.design.types import DesignStep, Mapping
from app.models.analysis import AnalysisRecord
from app.models.api_doc import ApiDocument
from app.models.design import IntegrationDesign
from app.models.project import Project, utc_now

router = APIRouter(prefix="/projects/{project_id}/design", tags=["integration design"])


class DocOption(BaseModel):
    id: int
    app_name: str
    title: str
    endpoint_count: int
    linked_to_project: bool


class EndpointOption(BaseModel):
    id: int
    doc_id: int
    app_name: str
    method: str
    path: str
    summary: str
    verification: str


class DesignOut(BaseModel):
    project_id: int
    saved: bool
    analysis_id: int | None
    has_analysis: bool
    trigger: str
    doc_ids: list[int]
    steps: list[DesignStep]
    mappings: list[Mapping]
    missing_documentation: list[str]
    mermaid: str
    available_docs: list[DocOption]
    endpoints: list[EndpointOption]
    updated_at: datetime | None


class DesignIn(BaseModel):
    trigger: str = Field(default="", max_length=1000)
    doc_ids: list[int] = Field(default_factory=list, max_length=50)
    steps: list[DesignStep] = Field(default_factory=list, max_length=100)
    mappings: list[Mapping] = Field(default_factory=list, max_length=500)


def _project(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")
    return project


def _latest_analysis(session: Session, project_id: int) -> AnalysisRecord | None:
    return session.exec(select(AnalysisRecord).where(AnalysisRecord.project_id == project_id).order_by(AnalysisRecord.id.desc())).first()


def _design(session: Session, project_id: int) -> IntegrationDesign:
    design = session.exec(select(IntegrationDesign).where(IntegrationDesign.project_id == project_id)).first()
    if design is None:
        linked = [d.id for d in session.exec(select(ApiDocument).where(ApiDocument.project_id == project_id)).all()]
        design = IntegrationDesign(project_id=project_id, doc_ids_json=json.dumps(linked))
    return design


def _steps(design: IntegrationDesign) -> list[DesignStep]:
    return [DesignStep(**s) for s in json.loads(design.steps_json)]


def _mappings(design: IntegrationDesign) -> list[Mapping]:
    return [Mapping(**m) for m in json.loads(design.mappings_json)]


def _save(session: Session, design: IntegrationDesign, steps=None, mappings=None) -> None:
    if steps is not None:
        design.steps_json = json.dumps([s.model_dump() for s in steps])
    if mappings is not None:
        design.mappings_json = json.dumps([m.model_dump() for m in mappings])
    design.updated_at = utc_now()
    session.add(design)
    session.commit()
    session.refresh(design)


def _out(session: Session, design: IntegrationDesign) -> DesignOut:
    doc_ids = json.loads(design.doc_ids_json)
    all_docs = session.exec(select(ApiDocument).order_by(ApiDocument.app_name)).all()
    pairs = service.endpoints_for_docs(session, doc_ids)
    counts: dict[int, int] = {}
    for ep, _ in service.endpoints_for_docs(session, [d.id for d in all_docs]):
        counts[ep.document_id] = counts.get(ep.document_id, 0) + 1
    steps = _steps(design)
    return DesignOut(
        project_id=design.project_id, saved=design.id is not None, analysis_id=design.analysis_id,
        has_analysis=_latest_analysis(session, design.project_id) is not None, trigger=design.trigger, doc_ids=doc_ids,
        steps=steps, mappings=_mappings(design), missing_documentation=json.loads(design.missing_docs_json),
        mermaid=build_mermaid(design.trigger, steps),
        available_docs=[DocOption(id=d.id, app_name=d.app_name, title=d.title or d.source_ref, endpoint_count=counts.get(d.id, 0),
                                  linked_to_project=d.project_id == design.project_id) for d in all_docs],
        endpoints=[EndpointOption(id=ep.id, doc_id=doc.id, app_name=doc.app_name, method=ep.method, path=ep.path,
                                  summary=ep.summary[:150], verification=ep.verification) for ep, doc in pairs[:5000]],
        updated_at=design.updated_at if design.id else None,
    )


@router.get("", response_model=DesignOut)
def get_design(project_id: int, session: Session = Depends(get_session)) -> DesignOut:
    _project(session, project_id)
    return _out(session, _design(session, project_id))


@router.put("", response_model=DesignOut)
def save_design(project_id: int, data: DesignIn, session: Session = Depends(get_session)) -> DesignOut:
    _project(session, project_id)
    design = _design(session, project_id)
    allowed = {ep.id: ep for ep, _ in service.endpoints_for_docs(session, data.doc_ids)}
    steps = []
    for i, step in enumerate(sorted(data.steps, key=lambda s: s.order), start=1):
        if step.endpoint_id is not None and step.endpoint_id not in allowed:
            raise HTTPException(400, f"Step {i}: endpoint {step.endpoint_id} is not in the selected documentation.")
        label = service.endpoint_label(allowed[step.endpoint_id]) if step.endpoint_id else ""
        status = step.match_status if step.endpoint_id or step.match_status == "no_endpoint" else "unmatched"
        steps.append(step.model_copy(update={"order": i, "endpoint_label": label, "match_status": status}))
    design.trigger = data.trigger
    design.doc_ids_json = json.dumps(data.doc_ids)
    _save(session, design, steps, data.mappings)
    return _out(session, design)


@router.post("/from-analysis", response_model=DesignOut)
def steps_from_analysis(project_id: int, session: Session = Depends(get_session)) -> DesignOut:
    _project(session, project_id)
    record = _latest_analysis(session, project_id)
    if record is None:
        raise HTTPException(400, "This project has no requirement analysis yet. Analyze it first, or add steps manually.")
    analysis = RequirementAnalysis.model_validate_json(record.result_json)
    design = _design(session, project_id)
    design.analysis_id = record.id
    design.trigger = f"{analysis.trigger.event} ({analysis.trigger.app})"
    steps = [DesignStep(order=s.order, app=s.app, action=s.action, description=s.description,
                        condition=s.condition, waits_for=s.waits_for) for s in analysis.steps]
    _save(session, design, steps)
    return _out(session, design)


@router.post("/match-endpoints", response_model=DesignOut)
def ai_match(project_id: int, session: Session = Depends(get_session), provider: AIProvider = Depends(get_ai_provider)) -> DesignOut:
    project = _project(session, project_id)
    design = _design(session, project_id)
    steps = _steps(design)
    if not steps:
        raise HTTPException(400, "Add steps first (from the analysis or manually).")
    pairs = service.endpoints_for_docs(session, json.loads(design.doc_ids_json))
    if not pairs:
        raise HTTPException(400, "Select imported documentation for this design first (API Doc Analyzer).")
    candidates = service.pick_candidates(pairs, steps)
    result = match_endpoints(
        provider,
        steps=[{"order": s.order, "app": s.app, "action": s.action, "description": s.description, "condition": s.condition} for s in steps],
        candidates=[service.candidate_line(ep, doc) for ep, doc in candidates],
        requirement=project.requirement,
    )
    steps = service.apply_choices(steps, result.choices, {ep.id: ep for ep, _ in candidates})
    design.missing_docs_json = json.dumps(result.missing_documentation)
    _save(session, design, steps)
    return _out(session, design)


@router.post("/suggest-mappings", response_model=DesignOut)
def ai_mappings(project_id: int, session: Session = Depends(get_session), provider: AIProvider = Depends(get_ai_provider)) -> DesignOut:
    project = _project(session, project_id)
    design = _design(session, project_id)
    pairs = service.endpoints_for_docs(session, json.loads(design.doc_ids_json))
    by_id = {ep.id: (ep, doc) for ep, doc in pairs}
    chosen = [by_id[s.endpoint_id] for s in _steps(design) if s.endpoint_id in by_id]
    if not chosen:
        raise HTTPException(400, "Choose endpoints for the steps first - mappings are based on their documentation.")
    record = _latest_analysis(session, project_id)
    data_items = [d.model_dump() for d in RequirementAnalysis.model_validate_json(record.result_json).data_to_transfer] if record else []

    result = suggest_mappings(provider, requirement=project.requirement, data_to_transfer=data_items,
                              endpoints=[service.endpoint_doc(ep, doc) for ep, doc in chosen])

    # Documentation text per app, to check that every proposed field really exists.
    docs_text: dict[str, str] = {}
    for ep, doc in pairs:
        docs_text[doc.app_name.lower()] = docs_text.get(doc.app_name.lower(), "") + " " + json.dumps(service.endpoint_doc(ep, doc))
    proposed = service.check_mappings(result.mappings, docs_text)
    manual = [m for m in _mappings(design) if m.evidence == "manual"]  # your own rows are kept
    notes = [f"Required target field with no source: {f}" for f in result.unmapped_required]
    if notes:
        design.missing_docs_json = json.dumps(json.loads(design.missing_docs_json) + notes)
    _save(session, design, mappings=manual + proposed)
    return _out(session, design)
