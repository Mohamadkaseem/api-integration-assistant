import pytest

from app.ai.deps import get_ai_provider
from app.ai.provider import AIError
from app.main import app
from tests.sample_analysis import SAMPLE_ANALYSIS

REQUIREMENT = "When a new company is created in HubSpot, create or update the Account in Zoho CRM."


class FakeProvider:
    """Stands in for Claude: records what it was asked and returns a fixed answer."""

    name = "fake"
    model = "fake-model"

    def __init__(self):
        self.calls = []

    def generate_structured(self, *, system, user, schema):
        self.calls.append({"system": system, "user": user})
        return SAMPLE_ANALYSIS


@pytest.fixture
def fake_ai():
    provider = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)


def make_project(client):
    return client.post("/api/projects", json={"name": "B", "requirement": REQUIREMENT}).json()["id"]


def test_ai_status_never_returns_the_key(client, monkeypatch):
    from pydantic import SecretStr

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr("sk-ant-REAL-SECRET-123"))
    body = client.get("/api/ai/status").json()
    assert set(body) == {"configured", "provider", "model", "env_file_found", "hint"}
    assert body["configured"] is True
    assert "REAL-SECRET" not in str(body)


def test_analyze_without_project_is_not_saved(client, fake_ai):
    response = client.post("/api/analysis", json={"requirement": REQUIREMENT})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] is None
    assert body["analysis"]["trigger"]["app"] == "HubSpot"
    assert "<requirement>" in fake_ai.calls[0]["user"]


def test_analyze_project_saves_and_latest_returns_it(client, fake_ai):
    project_id = make_project(client)
    assert client.get(f"/api/projects/{project_id}/analyses/latest").json() is None

    saved = client.post("/api/analysis", json={"requirement": REQUIREMENT, "project_id": project_id}).json()
    assert saved["id"] > 0

    latest = client.get(f"/api/projects/{project_id}/analyses/latest").json()
    assert latest["id"] == saved["id"]
    assert latest["analysis"]["readiness"] == "needs_clarification"


def test_clarification_answers_are_sent_to_the_ai(client, fake_ai):
    client.post(
        "/api/analysis",
        json={
            "requirement": REQUIREMENT,
            "clarifications": [
                {"question": "Which field identifies the company?", "answer": "The website domain"},
                {"question": "Unanswered question?", "answer": "  "},
            ],
        },
    )
    user_message = fake_ai.calls[0]["user"]
    assert "The website domain" in user_message
    assert "Unanswered question?" not in user_message  # blank answers are skipped


def test_latest_shows_newest_analysis(client, fake_ai):
    project_id = make_project(client)
    client.post("/api/analysis", json={"requirement": REQUIREMENT, "project_id": project_id})
    second = client.post("/api/analysis", json={"requirement": REQUIREMENT, "project_id": project_id}).json()
    assert client.get(f"/api/projects/{project_id}/analyses/latest").json()["id"] == second["id"]


def test_analyze_unknown_project_returns_404(client, fake_ai):
    response = client.post("/api/analysis", json={"requirement": REQUIREMENT, "project_id": 999})
    assert response.status_code == 404
    assert fake_ai.calls == []  # no AI call wasted


def test_requirement_too_short_is_rejected(client, fake_ai):
    assert client.post("/api/analysis", json={"requirement": "sync"}).status_code == 422


def test_ai_errors_become_clear_messages(client):
    def broken_provider():
        raise AIError("No Claude API key configured.", 503)

    app.dependency_overrides[get_ai_provider] = broken_provider
    try:
        response = client.post("/api/analysis", json={"requirement": REQUIREMENT})
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 503
    assert response.json() == {"detail": "No Claude API key configured."}


def test_deleting_project_deletes_its_analyses(client, fake_ai, session):
    from sqlmodel import select

    from app.models.analysis import AnalysisRecord

    project_id = make_project(client)
    client.post("/api/analysis", json={"requirement": REQUIREMENT, "project_id": project_id})
    client.delete(f"/api/projects/{project_id}")
    assert session.exec(select(AnalysisRecord)).all() == []
