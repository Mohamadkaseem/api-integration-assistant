"""Requirement Analyzer API.

  GET  /api/ai/status                         is a Claude API key configured?
  POST /api/analysis                          analyze a requirement (optionally save it to a project)
  GET  /api/projects/{id}/analyses/latest     the most recent saved analysis of a project
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.ai.deps import get_ai_provider
from app.ai.provider import AIProvider
from app.ai.requirement_analyzer import Clarification, RequirementAnalysis, analyze_requirement
from app.core.config import get_settings
from app.db import get_session
from app.models.analysis import AnalysisRecord
from app.models.project import Project

router = APIRouter(tags=["analysis"])


class AIStatus(BaseModel):
    configured: bool
    provider: str
    model: str


class AnalyzeRequest(BaseModel):
    requirement: str = Field(min_length=10, max_length=20_000)
    clarifications: list[Clarification] = Field(default_factory=list, max_length=50)
    project_id: int | None = None  # when set, the result is saved to this project


class AnalysisResponse(BaseModel):
    id: int | None  # None when not saved
    project_id: int | None
    requirement: str
    clarifications: list[Clarification]
    analysis: RequirementAnalysis
    ai_model: str
    created_at: datetime | None


def _to_response(record: AnalysisRecord) -> AnalysisResponse:
    return AnalysisResponse(
        id=record.id,
        project_id=record.project_id,
        requirement=record.requirement,
        clarifications=[Clarification(**c) for c in json.loads(record.clarifications_json)],
        analysis=RequirementAnalysis.model_validate_json(record.result_json),
        ai_model=record.ai_model,
        created_at=record.created_at,
    )


@router.get("/ai/status", response_model=AIStatus)
def ai_status() -> AIStatus:
    settings = get_settings()
    # Never return the key itself - only whether one exists.
    return AIStatus(configured=settings.ai_configured, provider="claude", model=settings.ai_model)


@router.post("/analysis", response_model=AnalysisResponse)
def analyze(
    data: AnalyzeRequest,
    session: Session = Depends(get_session),
    provider: AIProvider = Depends(get_ai_provider),
) -> AnalysisResponse:
    if data.project_id is not None and session.get(Project, data.project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {data.project_id} not found")

    result = analyze_requirement(provider, data.requirement, data.clarifications)

    if data.project_id is None:
        return AnalysisResponse(
            id=None, project_id=None, requirement=data.requirement, clarifications=data.clarifications,
            analysis=result, ai_model=provider.model, created_at=None,
        )

    record = AnalysisRecord(
        project_id=data.project_id,
        requirement=data.requirement,
        clarifications_json=json.dumps([c.model_dump() for c in data.clarifications]),
        result_json=result.model_dump_json(),
        ai_provider=provider.name,
        ai_model=provider.model,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _to_response(record)


@router.get("/projects/{project_id}/analyses/latest", response_model=AnalysisResponse | None)
def latest_analysis(project_id: int, session: Session = Depends(get_session)) -> AnalysisResponse | None:
    if session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    record = session.exec(
        select(AnalysisRecord)
        .where(AnalysisRecord.project_id == project_id)
        .order_by(AnalysisRecord.id.desc())
    ).first()
    return _to_response(record) if record else None
