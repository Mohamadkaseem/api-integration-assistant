from sqlmodel import select

from app.models.project import Project
from app.seed import STARTER_PROJECTS, seed_starter_projects

NEW_PROJECT = {
    "name": "Test project",
    "source_app": "HubSpot",
    "target_app": "Zoho CRM",
    "requirement": "Sync companies to accounts",
}


def test_list_is_empty_at_start(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_create_and_get_project(client):
    created = client.post("/api/projects", json=NEW_PROJECT)
    assert created.status_code == 201
    body = created.json()
    assert body["id"] > 0
    assert body["status"] == "planning"  # default

    fetched = client.get(f"/api/projects/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test project"


def test_create_requires_a_name(client):
    response = client.post("/api/projects", json={"name": ""})
    assert response.status_code == 422  # validation error


def test_create_rejects_unknown_status(client):
    response = client.post("/api/projects", json={"name": "X", "status": "flying"})
    assert response.status_code == 422


def test_update_changes_only_sent_fields(client):
    project_id = client.post("/api/projects", json=NEW_PROJECT).json()["id"]
    response = client.patch(f"/api/projects/{project_id}", json={"status": "testing"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "testing"
    assert body["name"] == "Test project"  # unchanged


def test_delete_project(client):
    project_id = client.post("/api/projects", json=NEW_PROJECT).json()["id"]
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_missing_project_returns_404(client):
    assert client.get("/api/projects/9999").status_code == 404
    assert client.patch("/api/projects/9999", json={"name": "X"}).status_code == 404
    assert client.delete("/api/projects/9999").status_code == 404


def test_seed_adds_starter_projects_once(session):
    seed_starter_projects(session)
    seed_starter_projects(session)  # second run must not duplicate
    projects = session.exec(select(Project)).all()
    assert len(projects) == len(STARTER_PROJECTS) == 3
