from pathlib import Path

from app.ai.deps import get_ai_provider
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def upload(client, name, project_id=None, app_name="Demo Sign"):
    data = {"app_name": app_name}
    if project_id:
        data["project_id"] = str(project_id)
    with open(FIXTURES / name, "rb") as f:
        return client.post("/api/docs/import", data=data, files={"file": (name, f, "application/octet-stream")})


def test_import_openapi_file_and_read_it_back(client):
    project_id = client.post("/api/projects", json={"name": "A"}).json()["id"]
    response = upload(client, "openapi3.json", project_id)
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["source_type"] == "openapi"
    assert doc["counts"]["spec"] == doc["endpoint_count"] == 3
    assert doc["auth_schemes"][0]["type"] == "oauth2"

    listed = client.get(f"/api/docs?project_id={project_id}").json()
    assert [d["id"] for d in listed] == [doc["id"]]
    detail = client.get(f"/api/docs/{doc['id']}").json()
    assert detail["endpoints"][0]["method"] == "POST"


def test_exactly_one_source_is_required(client):
    response = client.post("/api/docs/import", data={"app_name": "X", "text": "hello", "url": "https://example.com"})
    assert response.status_code == 400
    assert client.post("/api/docs/import", data={"app_name": "X"}).status_code == 400


def test_private_url_is_refused_with_message(client):
    response = client.post("/api/docs/import", data={"app_name": "X", "url": "http://127.0.0.1:8000/api/projects"})
    assert response.status_code == 400
    assert "private or local" in response.json()["detail"] or "own computer" in response.json()["detail"]


def test_openapi_import_works_without_api_key(client):
    def no_key():
        raise AssertionError("AI not needed for OpenAPI")

    app.dependency_overrides[get_ai_provider] = no_key
    try:
        assert upload(client, "swagger2.yaml").status_code == 201
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_delete_endpoint_and_document(client):
    doc = upload(client, "postman.json").json()
    first = doc["endpoints"][0]["id"]
    assert client.delete(f"/api/docs/{doc['id']}/endpoints/{first}").status_code == 204
    assert client.get(f"/api/docs/{doc['id']}").json()["endpoint_count"] == 1
    assert client.delete(f"/api/docs/{doc['id']}").status_code == 204
    assert client.get(f"/api/docs/{doc['id']}").status_code == 404


def test_deleting_project_keeps_its_documents(client):
    project_id = client.post("/api/projects", json={"name": "A"}).json()["id"]
    doc_id = upload(client, "openapi3.json", project_id).json()["id"]
    client.delete(f"/api/projects/{project_id}")
    assert client.get(f"/api/docs/{doc_id}").json()["project_id"] is None


def test_pasted_text_uses_ai_and_quote_check(client):
    from app.docs.ai_extractor import AIDocExtraction, AIEndpoint

    class FakeAI:
        name, model = "fake", "fake"

        def generate_structured(self, *, system, user, schema, max_tokens=16000):
            make = lambda m, p, q: AIEndpoint(method=m, path=p, summary="", auth="", parameters=[],
                                              request_body_example="", response_example="", evidence_quote=q)
            return AIDocExtraction(title="Zwayam", base_urls=[], auth_schemes=[], notes=[], endpoints=[
                make("PUT", "/candidates/{id}/status", "PUT /candidates/{id}/status"),
                make("DELETE", "/candidates/{id}", "DELETE /candidates/{id} removes a candidate"),  # invented
            ])

    app.dependency_overrides[get_ai_provider] = lambda: FakeAI()
    try:
        response = client.post("/api/docs/import", data={
            "app_name": "Zwayam", "text": "Update status with PUT /candidates/{id}/status and a JSON body."})
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source_type"] == "text"
    assert body["counts"] == {"spec": 0, "quoted": 1, "unverified": 1}


def test_pasted_text_without_api_key_explains_what_to_do(client, monkeypatch):
    from app.core.config import get_settings
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr(""))
    response = client.post("/api/docs/import", data={"app_name": "X", "text": "GET /things lists things"})
    assert response.status_code == 503
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]
