import httpx2
import pytest

from app.ai.deps import get_ai_provider
from app.ai.troubleshooter import CorrectedRequest, TroubleshootAnalysis
from app.http_runner.deps import get_resolver, get_transport
from app.main import app
from app.troubleshoot.rules import diagnose

ZOHO_INVALID = '{"data":[{"code":"INVALID_DATA","details":{"expected_data_type":"double","api_name":"Annual_Revenue"},"message":"invalid data","status":"error"}]}'


# ---------- Built-in rules ----------

@pytest.mark.parametrize("status,body,code,field,category", [
    (400, ZOHO_INVALID, "INVALID_DATA", "Annual_Revenue", "validation"),
    (400, '{"data":[{"code":"MANDATORY_NOT_FOUND","details":{"api_name":"Last_Name"},"message":"required field not found"}]}', "MANDATORY_NOT_FOUND", "Last_Name", "validation"),
    (202, '{"data":[{"code":"DUPLICATE_DATA","details":{"api_name":"Email","id":"123"},"message":"duplicate data"}]}', "DUPLICATE_DATA", "Email", "conflict"),
    (401, '{"code":"OAUTH_SCOPE_MISMATCH","details":{},"message":"invalid oauth scope"}', "OAUTH_SCOPE_MISMATCH", None, "permission"),
    (401, '{"code":"INVALID_TOKEN","details":{},"message":"invalid oauth token"}', "INVALID_TOKEN", None, "auth"),
    (400, '{"status":"error","category":"VALIDATION_ERROR","errors":[{"code":"INVALID_EMAIL","context":{"propertyName":["email"]}}]}', "VALIDATION_ERROR", "email", "validation"),
    (200, '{"error":"invalid_code"}', "invalid_code", None, "auth"),
])
def test_known_errors(status, body, code, field, category):
    d = diagnose(status, body)
    assert d.error_code == code and d.category == category
    if field:
        assert field in d.fields and field in d.suggestions[0]


def test_expected_type_is_mentioned():
    assert "double" in diagnose(400, ZOHO_INVALID).likely_causes[0]


def test_unknown_body_falls_back_to_status_and_retry_after():
    d = diagnose(429, "slow down", headers={"retry-after": "30"})
    assert d.category == "rate_limit" and d.retryable and "30 seconds" in d.suggestions[0]
    assert diagnose(418, "").category == "validation"  # any 4xx
    assert diagnose(503, "").retryable


def test_network_errors():
    assert diagnose(None, error_kind="dns").title == "Server name not found"
    assert "ALLOW_PRIVATE_NETWORK_REQUESTS" in diagnose(None, error_kind="blocked").suggestions[0]


# ---------- API ----------

def test_explain_pasted_error_is_free_and_needs_no_key(client):
    def no_ai():
        raise AssertionError("built-in explanations must not use AI")

    app.dependency_overrides[get_ai_provider] = no_ai
    try:
        response = client.post("/api/troubleshoot/explain", json={"status_code": 400, "response_body": ZOHO_INVALID})
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200
    assert response.json()["diagnosis"]["fields"] == ["Annual_Revenue"]


def test_explain_requires_something(client):
    assert client.post("/api/troubleshoot/explain", json={}).status_code == 400


def test_explain_from_history(client):
    def handler(request):
        return httpx2.Response(400, json={"data": [{"code": "MANDATORY_NOT_FOUND", "details": {"api_name": "Last_Name"}, "message": "required field not found"}]})

    app.dependency_overrides[get_transport] = lambda: httpx2.MockTransport(handler)
    app.dependency_overrides[get_resolver] = lambda: (lambda h: ["93.184.216.34"])
    try:
        sent = client.post("/api/requests/send", json={"confirm_write": True, "request": {
            "method": "POST", "url": "https://www.zohoapis.in/crm/v3/Leads", "body_type": "json", "body": '{"data":[{"Company":"Acme"}]}'}}).json()
    finally:
        app.dependency_overrides.pop(get_transport, None)
        app.dependency_overrides.pop(get_resolver, None)
    body = client.post("/api/troubleshoot/explain", json={"history_id": sent["history_id"]}).json()
    assert body["diagnosis"]["error_code"] == "MANDATORY_NOT_FOUND"
    assert body["context"]["request"]["url"].endswith("/Leads")


class FakeTroubleshooter:
    name, model = "fake", "fake"

    def __init__(self):
        self.calls = []

    def generate_structured(self, *, system, user, schema, max_tokens=16000):
        self.calls.append(user)
        return TroubleshootAnalysis(
            summary="Annual_Revenue must be a number.", likely_cause="Text sent to a currency field.",
            field_at_fault="Annual_Revenue", explanation="Zoho expects a number.", fix_steps=["Send 50000 instead of '50k'"],
            corrected_request=CorrectedRequest(method="POST", url="https://www.zohoapis.in/crm/v3/Accounts", query=[], headers=[],
                                               body_type="json", body='{"data":[{"Annual_Revenue":50000}]}', changes=["50k -> 50000"]),
            confidence="high", needs_more_info=[], used_documentation=True)


def test_ai_analysis_never_sees_secrets_and_uses_docs(client):
    from pathlib import Path

    with open(Path(__file__).parent / "fixtures" / "openapi3.json", "rb") as f:
        doc = client.post("/api/docs/import", data={"app_name": "Demo"}, files={"file": ("o.json", f, "application/json")}).json()
    endpoint_id = doc["endpoints"][0]["id"]

    fake = FakeTroubleshooter()
    app.dependency_overrides[get_ai_provider] = lambda: fake
    try:
        response = client.post("/api/troubleshoot/ai", json={
            "status_code": 400,
            "response_body": ZOHO_INVALID,
            "endpoint_id": endpoint_id,
            "request": {
                "method": "POST", "url": "https://www.zohoapis.in/crm/v3/Accounts?access_token=URLSECRET",
                "headers": [{"name": "Authorization", "value": "Zoho-oauthtoken HEADERSECRET"}],
                "body_type": "json", "body": '{"data":[{"Annual_Revenue":"50k","password":"BODYSECRET"}]}',
            },
        })
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis"]["field_at_fault"] == "Annual_Revenue"
    assert body["diagnosis"]["error_code"] == "INVALID_DATA"
    sent_to_ai = fake.calls[0]
    for secret in ("URLSECRET", "HEADERSECRET", "BODYSECRET"):
        assert secret not in sent_to_ai, secret
    assert "<endpoint_documentation>" in sent_to_ai and "/requests" in sent_to_ai
    assert "<builtin_diagnosis>" in sent_to_ai


def test_ai_without_key_explains(client, monkeypatch):
    from pydantic import SecretStr

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "anthropic_api_key", SecretStr(""))
    response = client.post("/api/troubleshoot/ai", json={"status_code": 400, "response_body": ZOHO_INVALID})
    assert response.status_code == 503
