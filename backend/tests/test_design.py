from pathlib import Path

import pytest

from app.ai.deps import get_ai_provider
from app.ai.designer import EndpointChoice, MappingResult, MatchResult, ProposedMapping
from app.design.mermaid import build_mermaid
from app.design.service import pick_candidates
from app.design.types import DesignStep
from app.main import app
from app.models.analysis import AnalysisRecord
from tests.sample_analysis import SAMPLE_ANALYSIS

FIXTURES = Path(__file__).parent / "fixtures"


# ---------- Diagram ----------

def test_mermaid_branches_and_rejoins():
    text = build_mermaid("New company", [
        DesignStep(order=1, app="Zoho CRM", action="search", description="Search account"),
        DesignStep(order=2, app="Zoho CRM", action="update", description="Update", condition="exists"),
        DesignStep(order=3, app="Zoho CRM", action="create", description="Create", condition="not found"),
        DesignStep(order=4, app="Integration", action="log", description='Log "result"'),
    ])
    assert "S1 --> D1" in text
    assert 'D1 -->|"exists"| S2' in text and 'D1 -->|"not found"| S3' in text
    assert "S2 --> S4" in text and "S3 --> S4" in text
    assert "#quot;result#quot;" in text  # quotes escaped so Mermaid does not break


def test_waits_for_is_an_edge_label():
    text = build_mermaid("Offer created", [
        DesignStep(order=1, app="Zoho Sign", action="send", description="Send to signatory"),
        DesignStep(order=2, app="Zwayam", action="update", description="Update status", waits_for="signatory signed"),
    ])
    assert 'S1 -->|"waits for: signatory signed"| S2' in text


# ---------- API ----------

def import_doc(client, name, app_name, project_id=None):
    data = {"app_name": app_name}
    if project_id:
        data["project_id"] = str(project_id)
    with open(FIXTURES / name, "rb") as f:
        return client.post("/api/docs/import", data=data, files={"file": (name, f, "application/json")}).json()


@pytest.fixture
def setup(client):
    project_id = client.post("/api/projects", json={"name": "B", "requirement": "Sync HubSpot companies to Zoho CRM"}).json()["id"]
    sign = import_doc(client, "openapi3.json", "Demo Sign", project_id)
    crm = import_doc(client, "postman.json", "Zoho CRM", project_id)
    other = import_doc(client, "swagger2.yaml", "Legacy CRM")  # not linked to the project
    return project_id, sign, crm, other


def test_default_design_uses_project_docs(client, setup):
    project_id, sign, crm, other = setup
    design = client.get(f"/api/projects/{project_id}/design").json()
    assert design["saved"] is False
    assert sorted(design["doc_ids"]) == sorted([sign["id"], crm["id"]])
    assert {d["id"] for d in design["available_docs"]} == {sign["id"], crm["id"], other["id"]}
    assert len(design["endpoints"]) == sign["endpoint_count"] + crm["endpoint_count"]
    assert design["mermaid"].startswith("flowchart TD")


def test_manual_save_validates_endpoints(client, setup):
    project_id, sign, crm, other = setup
    upsert_id = crm["endpoints"][0]["id"]
    body = {"trigger": "New company", "doc_ids": [crm["id"]], "steps": [
        {"order": 1, "app": "Zoho CRM", "action": "upsert", "description": "Create or update", "endpoint_id": upsert_id, "match_status": "manual"}],
        "mappings": [{"source_app": "HubSpot", "source_field": "name", "target_app": "Zoho CRM", "target_field": "Account_Name"}]}
    saved = client.put(f"/api/projects/{project_id}/design", json=body).json()
    assert saved["steps"][0]["endpoint_label"].startswith("POST ")
    assert "Account_Name" in str(saved["mappings"])
    assert "POST" in saved["mermaid"]

    other_endpoint = other["endpoints"][0]["id"]  # belongs to a doc that is not selected
    body["steps"][0]["endpoint_id"] = other_endpoint
    assert client.put(f"/api/projects/{project_id}/design", json=body).status_code == 400


def test_steps_from_analysis(client, setup, session):
    project_id, *_ = setup
    assert client.post(f"/api/projects/{project_id}/design/from-analysis").status_code == 400
    session.add(AnalysisRecord(project_id=project_id, requirement="x", clarifications_json="[]",
                               result_json=SAMPLE_ANALYSIS.model_dump_json(), ai_provider="fake", ai_model="fake"))
    session.commit()
    design = client.post(f"/api/projects/{project_id}/design/from-analysis").json()
    assert [s["action"] for s in design["steps"]] == ["read", "search", "update", "create", "log"]
    assert design["trigger"].startswith("A new company is created")
    assert "D1" in design["mermaid"]  # update/create became a decision


class FakeDesigner:
    name, model = "fake", "fake"

    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_structured(self, *, system, user, schema, max_tokens=16000):
        self.calls.append({"user": user, "schema": schema})
        return self.result


def test_ai_matching_rejects_invented_endpoints(client, setup):
    project_id, sign, crm, other = setup
    real = crm["endpoints"][0]["id"]
    manual_choice = crm["endpoints"][1]["id"]
    client.put(f"/api/projects/{project_id}/design", json={"trigger": "t", "doc_ids": [sign["id"], crm["id"]], "steps": [
        {"order": 1, "app": "Zoho CRM", "action": "upsert", "description": "Upsert account"},
        {"order": 2, "app": "Zwayam", "action": "update", "description": "Update candidate status"},
        {"order": 3, "app": "Integration", "action": "log", "description": "Log"},
        {"order": 4, "app": "Zoho CRM", "action": "read", "description": "Get account", "endpoint_id": manual_choice, "match_status": "manual"},
    ]})
    fake = FakeDesigner(MatchResult(
        choices=[EndpointChoice(step_order=1, endpoint_id=real, reason="upsert"),
                 EndpointChoice(step_order=2, endpoint_id=99999, reason="invented"),
                 EndpointChoice(step_order=3, endpoint_id=0, reason="no API call needed"),
                 EndpointChoice(step_order=4, endpoint_id=real, reason="should not override manual")],
        missing_documentation=["Zwayam: update candidate status"]))
    app.dependency_overrides[get_ai_provider] = lambda: fake
    try:
        design = client.post(f"/api/projects/{project_id}/design/match-endpoints").json()
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    status = [(s["match_status"], s["endpoint_id"]) for s in design["steps"]]
    assert status == [("matched", real), ("no_endpoint", None), ("unmatched", None), ("manual", manual_choice)]
    assert "rejected" in design["steps"][1]["match_note"]
    assert design["missing_documentation"] == ["Zwayam: update candidate status"]
    assert "<candidates>" in fake.calls[0]["user"] and f"{real} | Zoho CRM | POST" in fake.calls[0]["user"]
    assert "no documented endpoint" in design["mermaid"]


def test_large_catalog_is_filtered_by_relevance():
    class E:  # minimal stand-ins
        def __init__(self, i, path, summary):
            self.id, self.path, self.summary = i, path, summary

    class D:
        app_name = "Big API"

    pairs = [(E(i, f"/things/{i}", "unrelated"), D()) for i in range(1000)] + [(E(5000, "/candidates/{id}/status", "Update candidate status"), D())]
    picked = pick_candidates(pairs, [DesignStep(order=1, app="Zwayam", action="update", description="update candidate status")], limit=50)
    assert len(picked) == 50 and picked[0][0].id == 5000


def test_ai_mappings_are_checked_against_docs(client, setup):
    project_id, sign, crm, other = setup
    upsert = crm["endpoints"][0]["id"]
    create_request = next(e["id"] for e in sign["endpoints"] if e["method"] == "POST")
    client.put(f"/api/projects/{project_id}/design", json={"trigger": "t", "doc_ids": [sign["id"], crm["id"]], "steps": [
        {"order": 1, "app": "Demo Sign", "action": "create", "description": "Create request", "endpoint_id": create_request, "match_status": "manual"},
        {"order": 2, "app": "Zoho CRM", "action": "upsert", "description": "Upsert", "endpoint_id": upsert, "match_status": "manual"}],
        "mappings": [{"source_app": "X", "source_field": "my_field", "target_app": "Y", "target_field": "their_field", "evidence": "manual"}]})
    fake = FakeDesigner(MappingResult(mappings=[
        ProposedMapping(source_app="Demo Sign", source_field="request_name", target_app="Zoho CRM", target_field="Account_Name",
                        transform="", required=True, issue="none", notes=""),
        ProposedMapping(source_app="Demo Sign", source_field="actions[0].recipient_email", target_app="Zoho CRM", target_field="Made_Up_Field",
                        transform="", required=False, issue="none", notes=""),
    ], unmapped_required=["Zoho CRM: Owner"]))
    app.dependency_overrides[get_ai_provider] = lambda: fake
    try:
        design = client.post(f"/api/projects/{project_id}/design/suggest-mappings").json()
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    evidence = [(m["source_field"], m["evidence"]) for m in design["mappings"]]
    assert evidence == [("my_field", "manual"), ("request_name", "documented"), ("actions[0].recipient_email", "assumed")]
    assert any("Owner" in note for note in design["missing_documentation"])
    assert "<endpoints>" in fake.calls[0]["user"]


def test_ai_steps_need_prerequisites(client, setup):
    project_id, *_ = setup
    app.dependency_overrides[get_ai_provider] = lambda: FakeDesigner(None)
    try:
        assert client.post(f"/api/projects/{project_id}/design/match-endpoints").status_code == 400
        assert client.post(f"/api/projects/{project_id}/design/suggest-mappings").status_code == 400
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_deleting_project_deletes_design(client, setup, session):
    from sqlmodel import select

    from app.models.design import IntegrationDesign

    project_id, *_ = setup
    client.put(f"/api/projects/{project_id}/design", json={"trigger": "t"})
    client.delete(f"/api/projects/{project_id}")
    assert session.exec(select(IntegrationDesign)).all() == []
