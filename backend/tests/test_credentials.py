import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlmodel import select

from app.core.config import get_settings
from app.http_runner.deps import get_resolver, get_transport
from app.main import app
from app.models.credential import Credential
from app.security.crypto import CredentialDecryptError, decrypt_json, encrypt_json, get_fernet

ZOHO = {
    "name": "Zoho CRM sandbox", "app_name": "Zoho CRM", "type": "oauth2", "provider": "zoho", "data_center": "in",
    "client_id": "1000.CLIENTID12345", "client_secret": "CLIENTSECRET-XYZ", "scopes": "ZohoCRM.modules.ALL",
}


class FakeNet:
    """Mock internet: a Zoho-like token server plus an API that checks the access token."""

    def __init__(self):
        self.calls = []
        self.token_responses = []
        self.valid_tokens = {"NEW-ACCESS-1", "NEW-ACCESS-2"}

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.calls.append(request)
        if request.url.path == "/oauth/v2/token":
            return httpx2.Response(200, json=self.token_responses.pop(0))
        token = request.headers.get("authorization", "").split(" ", 1)[-1]
        if token not in self.valid_tokens:
            return httpx2.Response(401, json={"code": "INVALID_TOKEN"})
        return httpx2.Response(200, json={"data": [{"Account_Name": "Acme"}]})

    def form(self, i):
        return parse_qs(self.calls[i].content.decode())


@pytest.fixture
def net():
    fake = FakeNet()
    app.dependency_overrides[get_transport] = lambda: httpx2.MockTransport(fake)
    app.dependency_overrides[get_resolver] = lambda: (lambda host: ["93.184.216.34"])
    yield fake
    app.dependency_overrides.pop(get_transport, None)
    app.dependency_overrides.pop(get_resolver, None)


def test_encryption_round_trip_and_wrong_key(monkeypatch):
    token = encrypt_json({"password": "s3cret"})
    assert "s3cret" not in token
    assert decrypt_json(token) == {"password": "s3cret"}
    monkeypatch.setattr(get_settings(), "credentials_key", SecretStr(Fernet.generate_key().decode()))
    get_fernet.cache_clear()
    with pytest.raises(CredentialDecryptError):
        decrypt_json(token)


def test_secrets_are_encrypted_and_never_returned(client, session):
    response = client.post("/api/credentials", json={
        "name": "HubSpot key", "type": "api_key", "key_name": "X-API-Key", "key_value": "hubspot-super-secret-value"})
    assert response.status_code == 201
    body = response.json()
    assert body["secret_hint"] == "…alue"
    assert "hubspot-super-secret-value" not in json.dumps(client.get("/api/credentials").json())
    row = session.exec(select(Credential)).one()
    assert "hubspot-super-secret-value" not in row.secret_encrypted + row.public_json


def test_update_keeps_secret_when_left_blank(client, session):
    cred_id = client.post("/api/credentials", json={"name": "T", "type": "bearer", "token": "first-token-123"}).json()["id"]
    client.patch(f"/api/credentials/{cred_id}", json={"name": "Renamed", "token": ""})
    row = session.get(Credential, cred_id)
    assert row.name == "Renamed" and decrypt_json(row.secret_encrypted)["token"] == "first-token-123"
    client.patch(f"/api/credentials/{cred_id}", json={"token": "second-token-456"})
    session.refresh(row)
    assert decrypt_json(row.secret_encrypted)["token"] == "second-token-456"


def test_zoho_self_client_code_exchange(client, net):
    cred = client.post("/api/credentials", json=ZOHO).json()
    assert cred["status"] == "needs_authorization"
    net.token_responses.append({"access_token": "NEW-ACCESS-1", "refresh_token": "REFRESH-1", "expires_in": 3600,
                                "api_domain": "https://www.zohoapis.in", "token_type": "Bearer"})
    response = client.post(f"/api/credentials/{cred['id']}/oauth/exchange-code", json={"code": "1000.grantcode"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready" and body["has_refresh_token"]
    assert body["settings"]["api_domain"] == "https://www.zohoapis.in"
    request = net.calls[0]
    assert str(request.url) == "https://accounts.zoho.in/oauth/v2/token"  # India data centre
    form = net.form(0)
    assert form["grant_type"] == ["authorization_code"] and form["code"] == ["1000.grantcode"]
    assert form["client_secret"] == ["CLIENTSECRET-XYZ"] and "redirect_uri" not in form
    assert "REFRESH-1" not in json.dumps(body)


def test_zoho_error_with_status_200_is_explained(client, net):
    cred_id = client.post("/api/credentials", json=ZOHO).json()["id"]
    net.token_responses.append({"error": "invalid_code"})
    response = client.post(f"/api/credentials/{cred_id}/oauth/exchange-code", json={"code": "old-code"})
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]
    assert client.get("/api/credentials").json()[0]["status"] == "error"


def test_missing_refresh_token_is_reported(client, net):
    cred_id = client.post("/api/credentials", json=ZOHO).json()["id"]
    net.token_responses.append({"access_token": "A", "expires_in": 3600})
    response = client.post(f"/api/credentials/{cred_id}/oauth/exchange-code", json={"code": "c0de"})
    assert response.status_code == 400 and "no refresh token" in response.json()["detail"].lower()


def connected_zoho(client, net, session, expires_in_seconds):
    cred_id = client.post("/api/credentials", json=ZOHO).json()["id"]
    net.token_responses.append({"access_token": "OLD-ACCESS", "refresh_token": "REFRESH-1", "expires_in": 3600})
    client.post(f"/api/credentials/{cred_id}/oauth/exchange-code", json={"code": "c0de"})
    row = session.get(Credential, cred_id)
    session.refresh(row)
    public = json.loads(row.public_json)
    public["expires_at"] = time.time() + expires_in_seconds
    row.public_json = json.dumps(public)
    session.add(row)
    session.commit()
    net.calls.clear()
    return cred_id


GET_ACCOUNTS = {"method": "GET", "url": "https://www.zohoapis.in/crm/v3/Accounts"}


def test_expired_token_is_refreshed_before_sending(client, net, session):
    cred_id = connected_zoho(client, net, session, expires_in_seconds=-10)  # already expired
    net.token_responses.append({"access_token": "NEW-ACCESS-1", "expires_in": 3600})
    response = client.post("/api/requests/send", json={"request": GET_ACCOUNTS, "credential_id": cred_id})
    assert response.json()["status_code"] == 200
    assert net.form(0)["grant_type"] == ["refresh_token"] and net.form(0)["refresh_token"] == ["REFRESH-1"]
    assert net.calls[1].headers["authorization"] == "Zoho-oauthtoken NEW-ACCESS-1"
    saved = json.dumps(client.get(f"/api/requests/history/{response.json()['history_id']}").json())
    for secret in ("NEW-ACCESS-1", "REFRESH-1", "CLIENTSECRET-XYZ"):
        assert secret not in saved
    assert '"credential_id": %d' % cred_id in saved


def test_401_triggers_one_refresh_and_retry(client, net, session):
    cred_id = connected_zoho(client, net, session, expires_in_seconds=3000)  # looks valid, but server rejects OLD-ACCESS
    net.token_responses.append({"access_token": "NEW-ACCESS-2", "expires_in": 3600})
    response = client.post("/api/requests/send", json={"request": GET_ACCOUNTS, "credential_id": cred_id})
    assert response.json()["status_code"] == 200
    assert [c.url.path for c in net.calls] == ["/crm/v3/Accounts", "/oauth/v2/token", "/crm/v3/Accounts"]


def test_not_connected_credential_gives_clear_error(client, net):
    cred_id = client.post("/api/credentials", json=ZOHO).json()["id"]
    response = client.post("/api/requests/send", json={"request": GET_ACCOUNTS, "credential_id": cred_id})
    assert response.status_code == 400 and "not connected" in response.json()["detail"]


def test_browser_sign_in_flow(client, net):
    cred_id = client.post("/api/credentials", json={**ZOHO, "data_center": "com"}).json()["id"]
    start = client.get(f"/api/credentials/{cred_id}/oauth/authorize-url").json()
    url = urlsplit(start["url"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.zoho.com" and query["access_type"] == ["offline"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/oauth/callback"]

    # Zoho redirects back, telling us the account actually lives in the EU data centre.
    net.token_responses.append({"access_token": "NEW-ACCESS-1", "refresh_token": "R", "expires_in": 3600})
    back = client.get("/api/oauth/callback", params={"state": query["state"][0], "code": "abc",
                                                     "accounts-server": "https://accounts.zoho.eu"}, follow_redirects=False)
    assert back.status_code == 303 and back.headers["location"] == f"http://localhost:3000/credentials?connected={cred_id}"
    assert str(net.calls[0].url) == "https://accounts.zoho.eu/oauth/v2/token"
    assert net.form(0)["redirect_uri"] == ["http://localhost:8000/api/oauth/callback"]
    assert client.get("/api/credentials").json()[0]["settings"]["data_center"] == "eu"

    replay = client.get("/api/oauth/callback", params={"state": query["state"][0], "code": "abc"}, follow_redirects=False)
    assert "oauth_error" in replay.headers["location"]  # a state can be used only once


def test_generic_oauth_with_basic_client_auth(client, net):
    cred_id = client.post("/api/credentials", json={
        "name": "Other", "type": "oauth2", "provider": "generic", "client_id": "cid", "client_secret": "csecret",
        "token_url": "https://auth.example.com/oauth/v2/token", "client_auth_method": "basic"}).json()["id"]
    net.token_responses.append({"access_token": "NEW-ACCESS-1", "refresh_token": "R", "expires_in": 60})
    assert client.post(f"/api/credentials/{cred_id}/oauth/exchange-code", json={"code": "abcd"}).status_code == 200
    request = net.calls[0]
    assert request.headers["authorization"].startswith("Basic ")
    assert "client_secret" not in net.form(0)
    assert net.form(0)["redirect_uri"] == ["http://localhost:8000/api/oauth/callback"]
