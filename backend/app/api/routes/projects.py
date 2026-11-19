"""Projects API - the four basic "CRUD" actions:

  GET    /api/projects        list all projects
  POST   /api/projects        create a project
  GET    /api/projects/{id}   view one project
  PATCH  /api/projects/{id}   edit some fields of a project
  DELETE /api/projects/{id}   delete a project
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.db import get_session
from app.models.project import Project, ProjectCreate, ProjectRead, ProjectUpdate, utc_now

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_or_404(session: Session, project_id: int) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return project


@router.get("", response_model=list[ProjectRead])
def list_projects(session: Session = Depends(get_session)) -> list[Project]:
    # In the order they were created (A, B, C, then your new ones).
    return list(session.exec(select(Project).order_by(Project.id)).all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(data: ProjectCreate, session: Session = Depends(get_session)) -> Project:
    project = Project.model_validate(data)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, session: Session = Depends(get_session)) -> Project:
    return _get_or_404(session, project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int, data: ProjectUpdate, session: Session = Depends(get_session)
) -> Project:
    project = _get_or_404(session, project_id)
    # Only change the fields that were actually sent.
    changes = data.model_dump(exclude_unset=True)
    project.sqlmodel_update(changes)
    project.updated_at = utc_now()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, session: Session = Depends(get_session)) -> None:
    project = _get_or_404(session, project_id)
    session.delete(project)
    session.commit()
