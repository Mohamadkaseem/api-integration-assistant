import base64
import io
import json
import zipfile
from pathlib import Path

import httpx2
import pytest
from docx import Document

from app.ai.deps import get_ai_provider
from app.ai.handover_writer import AITestCase, HandoverWriting
from app.http_runner.deps import get_resolver, get_transport
from app.main import app
from app.models.analysis import AnalysisRecord
from tests.sample_analysis import SAMPLE_ANALYSIS

FIXTURES = Path(__file__).parent / "fixtures"
SECRETS = ("CLIENTSECRET-XYZ", "REFRESH-TOKEN-1", "ACCESS-TOKEN-1", "HEADER-SECRET-9")


def make_png(width=4, height=3) -> str:
    """A small valid PNG (white pixels), built with the standard library only."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return base64.b64encode(png).decode()


TINY_PNG = make_png()


@pytest.fixture
def full_project(client, session):
    project_id = client.post("/api/projects", json={"name": "Project B: HubSpot → Zoho CRM", "source_app": "HubSpot", "target_app": "Zoho CRM",
                                                    "requirement": "Sync HubSpot companies into Zoho CRM Accounts."}).json()["id"]
    with open(FIXTURES / "postman.json", "rb") as f:
        doc = client.post("/api/docs/import", data={"app_name": "Zoho CRM", "project_id": str(project_id)},
                          files={"file": ("p.json", f, "application/json")}).json()
    session.add(AnalysisRecord(project_id=project_id, requirement="x", clarifications_json="[]",
                               result_json=SAMPLE_ANALYSIS.model_dump_json(), ai_provider="fake", ai_model="fake"))
    session.commit()
    client.post(f"/api/projects/{project_id}/design/from-analysis")
    design = client.get(f"/api/projects/{project_id}/design").json()
    steps = design["steps"]
    steps[3]["endpoint_id"], steps[3]["match_status"] = doc["endpoints"][0]["id"], "manual"   # create -> upsert
    steps[0]["match_status"] = "no_endpoint"
    client.put(f"/api/projects/{project_id}/design", json={"trigger": design["trigger"], "doc_ids": design["doc_ids"], "steps": steps, "mappings": [
        {"source_app": "HubSpot", "source_field": "properties.name", "target_app": "Zoho CRM", "target_field": "Account_Name", "required": True, "issue": "nested", "evidence": "assumed"}]})

    # A saved Zoho OAuth credential (secrets must never appear in the handover)
    import time

    from app.credentials import service
    from app.models.credential import Credential
    cred = Credential(name="Zoho CRM sandbox", app_name="Zoho CRM", type="oauth2", status="ready")
    service.save(session, cred, {"provider": "zoho", "data_center": "in", "scopes": "ZohoCRM.modules.ALL", "token_prefix": "Zoho-oauthtoken",
                                 "expires_at": time.time() + 3000},
                 {"client_id": "1000.CID", "client_secret": "CLIENTSECRET-XYZ", "refresh_token": "REFRESH-TOKEN-1", "access_token": "ACCESS-TOKEN-1"})

    # A tested request with a typed secret header
    app.dependency_overrides[get_transport] = lambda: httpx2.MockTransport(lambda r: httpx2.Response(201, json={"data": [{"code": "SUCCESS"}]}))
    app.dependency_overrides[get_resolver] = lambda: (lambda h: ["93.184.216.34"])
    try:
        client.post("/api/requests/send", json={"confirm_write": True, "project_id": project_id, "request": {
            "method": "POST", "url": "https://www.zohoapis.in/crm/v3/Accounts/upsert",
            "headers": [{"name": "Authorization", "value": "Zoho-oauthtoken HEADER-SECRET-9"}],
            "body_type": "json", "body": '{"data":[{"Account_Name":"Acme"}]}'}})
    finally:
        app.dependency_overrides.pop(get_transport, None)
        app.dependency_overrides.pop(get_resolver, None)
    return project_id


def test_preview_has_all_sections(client, full_project):
    body = client.get(f"/api/projects/{full_project}/handover").json()
    d = body["data"]
    assert d["has_analysis"] and d["has_design"]
    assert len(d["steps"]) == 5 and d["endpoints"][0]["method"] == "POST"
    assert d["endpoints"][0]["full_url"] == "https://www.example.com/crm/v3/Accounts/upsert"  # Postman {{base_url}} filled in
    assert any("Zoho in" in a["description"] and "ZohoCRM.modules.ALL" in a["description"] for a in d["authentication"])
    assert {e["code"] for e in d["errors"]} >= {"INVALID_DATA", "MANDATORY_NOT_FOUND", "OAUTH_SCOPE_MISMATCH"}
    titles = [t["title"] for t in d["test_cases"]]
    assert "Happy path" in titles and any(t.startswith("Branch:") for t in titles) and "Expired access token" in titles
    assert any("assumed" in p for p in d["open_points"]) and any("no documented endpoint" in p for p in d["open_points"])
    assert any("Open question" in p for p in d["open_points"])
    assert d["samples"][0]["status"] == "201"
    md = body["markdown"]
    assert "```mermaid" in md and "## 7. Test cases" in md
    for secret in SECRETS:
        assert secret not in json.dumps(body), secret


def test_markdown_download(client, full_project):
    response = client.get(f"/api/projects/{full_project}/handover/markdown")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="Project-B-HubSpot-Zoho-CRM-handover.md"'
    assert response.text.startswith("# Project B")


def test_word_document_is_valid_and_has_no_secrets(client, full_project):
    response = client.post(f"/api/projects/{full_project}/handover/docx", json={"diagram_png_base64": TINY_PNG})
    assert response.status_code == 200 and response.headers["content-disposition"].endswith('.docx"')
    document = Document(io.BytesIO(response.content))
    headings = [p.text for p in document.paragraphs if p.style.name.startswith("Heading")]
    assert "1. Overview" in headings and "7. Test cases" in headings and "9. Assumptions & open points" in headings
    assert len(document.inline_shapes) == 1  # the diagram picture
    xml = zipfile.ZipFile(io.BytesIO(response.content)).read("word/document.xml").decode()
    assert "Account_Name" in xml
    for secret in SECRETS:
        assert secret not in xml, secret


def test_bad_diagram_image_does_not_break_export(client, full_project):
    response = client.post(f"/api/projects/{full_project}/handover/docx", json={"diagram_png_base64": "bm90IGFuIGltYWdl"})
    assert response.status_code == 200


def test_empty_project_still_produces_a_document(client):
    project_id = client.post("/api/projects", json={"name": "Empty"}).json()["id"]
    d = client.get(f"/api/projects/{project_id}/handover").json()["data"]
    assert d["open_points"][0].startswith("No integration design yet")
    assert d["test_cases"] == []
    assert client.post(f"/api/projects/{project_id}/handover/docx", json={}).status_code == 200
    assert client.get("/api/projects/999/handover").status_code == 404


def test_ai_adds_summary_and_test_cases(client, full_project):
    class FakeWriter:
        name, model = "fake", "fake"
        seen = ""

        def generate_structured(self, *, system, user, schema, max_tokens=16000):
            FakeWriter.seen = user
            return HandoverWriting(summary="This integration keeps Zoho CRM Accounts in sync with HubSpot companies.",
                                   extra_test_cases=[AITestCase(id="AI-01", title="Company name with emoji", preconditions="", steps="", expected="Saved unchanged")])

    app.dependency_overrides[get_ai_provider] = lambda: FakeWriter()
    try:
        body = client.post(f"/api/projects/{full_project}/handover/ai").json()
        body = client.post(f"/api/projects/{full_project}/handover/ai").json()  # running twice must not duplicate
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    d = body["data"]
    assert d["ai_summary"].startswith("This integration")
    assert [t["id"] for t in d["test_cases"] if t["source"] == "ai"] == ["AI-01"]
    assert "This integration keeps" in body["markdown"]
    for secret in SECRETS:
        assert secret not in FakeWriter.seen


def test_browser_can_read_download_filename(client, full_project):
    """Without Access-Control-Expose-Headers the browser cannot see the file name (regression)."""
    response = client.get(f"/api/projects/{full_project}/handover/markdown", headers={"Origin": "http://localhost:3000"})
    assert "content-disposition" in response.headers.get("access-control-expose-headers", "").lower()
