import httpx2
import pytest

from app.api.routes.requests import get_resolver, get_transport
from app.main import app


@pytest.fixture
def server():
    """A mock API server; records what it received."""
    received = []

    def handler(request):
        received.append(request)
        if request.url.path == "/fail":
            return httpx2.Response(400, json={"code": "INVALID_DATA", "message": "Invalid value for field"})
        return httpx2.Response(200, json={"data": [{"code": "SUCCESS"}]}, headers={"set-cookie": "session=abc"})

    app.dependency_overrides[get_transport] = lambda: httpx2.MockTransport(handler)
    app.dependency_overrides[get_resolver] = lambda: (lambda host: ["93.184.216.34"])
    yield received
    app.dependency_overrides.pop(get_transport, None)
    app.dependency_overrides.pop(get_resolver, None)


SECRET_REQUEST = {
    "method": "POST",
    "url": "https://www.zohoapis.com/crm/v3/Accounts/upsert?access_token=URLSECRET",
    "headers": [{"name": "Authorization", "value": "Zoho-oauthtoken HEADERSECRET"}, {"name": "X-Trace", "value": "visible"}],
    "params": [{"name": "api_key", "value": "PARAMSECRET"}],
    "body_type": "json",
    "body": '{"data": [{"Account_Name": "Acme"}]}',
    "auth": {"type": "bearer", "token": "BEARERSECRET", "token_prefix": "Zoho-oauthtoken"},
}


def test_write_requests_need_confirmation(client, server):
    response = client.post("/api/requests/send", json={"request": SECRET_REQUEST})
    assert response.status_code == 409
    assert server == []  # nothing was sent


def test_send_and_history_never_store_secrets(client, server):
    response = client.post("/api/requests/send", json={"request": SECRET_REQUEST, "confirm_write": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status_code"] == 200 and body["history_id"] > 0
    # The real request did carry the credentials:
    assert server[0].headers["authorization"] == "Zoho-oauthtoken BEARERSECRET"

    detail = client.get(f"/api/requests/history/{body['history_id']}").json()
    saved = str(detail)
    for secret in ("URLSECRET", "HEADERSECRET", "PARAMSECRET", "BEARERSECRET", "session=abc"):
        assert secret not in saved, secret
    assert "visible" in saved  # non-secret headers are kept
    assert detail["request"]["auth"]["type"] == "bearer"
    assert "SUCCESS" in detail["response_body"]


def test_get_needs_no_confirmation_and_stats_count(client, server):
    client.post("/api/requests/send", json={"request": {"method": "GET", "url": "https://api.example.com/ok"}})
    client.post("/api/requests/send", json={"request": {"method": "GET", "url": "https://api.example.com/fail"}})
    client.post("/api/requests/send", json={"request": {"method": "GET", "url": "http://localhost/x"}})  # blocked
    assert client.get("/api/requests/stats").json() == {"total": 3, "successful": 1, "failed": 2}
    history = client.get("/api/requests/history").json()
    assert [h["status_code"] for h in history] == [None, 400, 200]  # newest first
    assert history[0]["error_kind"] == "blocked"


def test_delete_history_item(client, server):
    history_id = client.post("/api/requests/send", json={"request": {"method": "GET", "url": "https://api.example.com/ok"}}).json()["history_id"]
    assert client.delete(f"/api/requests/history/{history_id}").status_code == 204
    assert client.get(f"/api/requests/history/{history_id}").status_code == 404


def test_tokens_in_response_and_request_bodies_are_masked_in_history(client):
    """OAuth token endpoints return access/refresh tokens in the body; servers may echo our token back."""

    def handler(request):
        return httpx2.Response(200, json={
            "access_token": "1000.ACCESS.SECRET", "refresh_token": "1000.REFRESH.SECRET", "expires_in": 3600,
            "echo": "you sent Zoho-oauthtoken TYPEDTOKEN123",
        })

    app.dependency_overrides[get_transport] = lambda: httpx2.MockTransport(handler)
    app.dependency_overrides[get_resolver] = lambda: (lambda host: ["93.184.216.34"])
    try:
        response = client.post("/api/requests/send", json={"confirm_write": True, "request": {
            "method": "POST", "url": "https://accounts.zoho.com/oauth/v2/token",
            "body_type": "json", "body": '{"client_secret": "CLIENTSECRET", "grant_type": "refresh_token"}',
            "auth": {"type": "bearer", "token": "TYPEDTOKEN123"}}})
    finally:
        app.dependency_overrides.pop(get_transport, None)
        app.dependency_overrides.pop(get_resolver, None)

    live = response.json()
    assert "1000.ACCESS.SECRET" in live["body"]  # you still SEE the token in the live response

    saved = str(client.get(f"/api/requests/history/{live['history_id']}").json())
    for secret in ("1000.ACCESS.SECRET", "1000.REFRESH.SECRET", "TYPEDTOKEN123", "CLIENTSECRET"):
        assert secret not in saved, secret
    assert "3600" in saved and "refresh_token" in saved  # non-secret data and field names are kept
