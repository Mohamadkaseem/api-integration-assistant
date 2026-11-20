"""Developer handover document.

  GET  /api/projects/{id}/handover            all handover data + Markdown (for the preview)
  GET  /api/projects/{id}/handover/markdown   download as .md
  POST /api/projects/{id}/handover/docx       download as Word (.docx); optional diagram picture
  POST /api/projects/{id}/handover/ai         Claude adds a summary + extra test cases (optional)
"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.ai.deps import get_ai_provider
from app.ai.handover_writer import write_handover
from app.ai.provider import AIProvider
from app.db import get_session
from app.handover.data import HandoverData, gather
from app.handover.render import to_docx, to_markdown
from app.models.handover import HandoverNotes
from app.models.project import utc_now

router = APIRouter(prefix="/projects/{project_id}/handover", tags=["handover"])


class HandoverOut(BaseModel):
    data: HandoverData
    markdown: str


class DocxIn(BaseModel):
    diagram_png_base64: str | None = Field(default=None, max_length=15_000_000)


def _gather(session: Session, project_id: int) -> HandoverData:
    try:
        return gather(session, project_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


def _filename(data: HandoverData, ext: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", data.project_name).strip("-")[:60] or "project"
    return f"{slug}-handover.{ext}"


@router.get("", response_model=HandoverOut)
def preview(project_id: int, session: Session = Depends(get_session)) -> HandoverOut:
    data = _gather(session, project_id)
    return HandoverOut(data=data, markdown=to_markdown(data))


@router.get("/markdown")
def download_markdown(project_id: int, session: Session = Depends(get_session)) -> Response:
    data = _gather(session, project_id)
    return Response(to_markdown(data), media_type="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_filename(data, "md")}"'})


@router.post("/docx")
def download_docx(project_id: int, body: DocxIn, session: Session = Depends(get_session)) -> Response:
    data = _gather(session, project_id)
    return Response(
        to_docx(data, body.diagram_png_base64),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data, "docx")}"'},
    )


@router.post("/ai", response_model=HandoverOut)
def improve_with_ai(project_id: int, session: Session = Depends(get_session), provider: AIProvider = Depends(get_ai_provider)) -> HandoverOut:
    data = _gather(session, project_id)
    data.ai_summary = ""
    data.test_cases = [t for t in data.test_cases if t.source != "ai"]
    writing = write_handover(provider, data.model_dump_json(exclude={"mermaid", "samples"}))
    notes = session.exec(select(HandoverNotes).where(HandoverNotes.project_id == project_id)).first() or HandoverNotes(project_id=project_id)
    notes.ai_summary = writing.summary
    notes.ai_test_cases_json = json.dumps([t.model_dump() for t in writing.extra_test_cases[:8]])
    notes.updated_at = utc_now()
    session.add(notes)
    session.commit()
    data = _gather(session, project_id)
    return HandoverOut(data=data, markdown=to_markdown(data))
