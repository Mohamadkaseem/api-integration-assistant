import base64
import json

import httpx2

from app.http_runner.redact import MASK, redact_url
from app.http_runner.runner import AuthConfig, KeyValue, OutgoingRequest, build_headers, build_url, send_request


def public(_host):
    return ["93.184.216.34"]


def mock(handler):
    return httpx2.MockTransport(handler)


def test_query_params_are_added_and_disabled_ones_skipped():
    req = OutgoingRequest(method="GET", url="https://api.example.com/items?a=1",
                          params=[KeyValue(name="b", value="2"), KeyValue(name="c", value="3", enabled=False)])
    assert build_url(req) == "https://api.example.com/items?a=1&b=2"


def test_auth_types_build_correct_headers():
    bearer = build_headers(OutgoingRequest(method="GET", url="https://x.io", auth=AuthConfig(type="bearer", token="abc")))
    assert bearer["Authorization"] == "Bearer abc"
    zoho = build_headers(OutgoingRequest(method="GET", url="https://x.io",
                                         auth=AuthConfig(type="bearer", token="abc", token_prefix="Zoho-oauthtoken")))
    assert zoho["Authorization"] == "Zoho-oauthtoken abc"
    basic = build_headers(OutgoingRequest(method="GET", url="https://x.io", auth=AuthConfig(type="basic", username="u", password="p")))
    assert basic["Authorization"] == "Basic " + base64.b64encode(b"u:p").decode()
    api_key = build_headers(OutgoingRequest(method="GET", url="https://x.io",
                                            auth=AuthConfig(type="api_key", key_name="X-API-Key", key_value="k1")))
    assert api_key["X-API-Key"] == "k1"
    in_query = OutgoingRequest(method="GET", url="https://x.io/a",
                               auth=AuthConfig(type="api_key", key_name="api_key", key_value="k2", key_in="query"))
    assert build_url(in_query) == "https://x.io/a?api_key=k2"


def test_json_body_is_sent_with_content_type():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        seen["ct"] = request.headers.get("content-type")
        return httpx2.Response(201, json={"id": 7})

    result = send_request(OutgoingRequest(method="POST", url="https://api.example.com/x", body_type="json",
                                          body='{"name": "Acme"}'), resolve=public, transport=mock(handler))
    assert result.ok and result.status_code == 201
    assert json.loads(result.body) == {"id": 7}
    assert json.loads(seen["body"]) == {"name": "Acme"}
    assert seen["ct"] == "application/json"


def test_invalid_json_is_caught_before_sending():
    def handler(request):
        raise AssertionError("must not be sent")

    result = send_request(OutgoingRequest(method="POST", url="https://api.example.com/x", body_type="json",
                                          body='{"name": }'), resolve=public, transport=mock(handler))
    assert not result.ok and result.error_kind == "invalid"
    assert "not valid JSON" in result.error_message


def test_private_address_blocked_unless_allowed():
    req = OutgoingRequest(method="GET", url="http://127.0.0.1:9000/health")
    blocked = send_request(req, resolve=lambda h: ["127.0.0.1"], transport=mock(lambda r: httpx2.Response(200)))
    assert blocked.error_kind == "blocked"
    allowed = send_request(req, allow_private=True, transport=mock(lambda r: httpx2.Response(200, text="ok")))
    assert allowed.status_code == 200


def test_redirects_are_shown_not_followed():
    def handler(request):
        return httpx2.Response(302, headers={"location": "https://elsewhere.example.com/"})

    result = send_request(OutgoingRequest(method="GET", url="https://api.example.com/old"), resolve=public, transport=mock(handler))
    assert result.status_code == 302
    assert result.headers["location"] == "https://elsewhere.example.com/"


def test_binary_response_is_not_dumped_as_text():
    def handler(request):
        return httpx2.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4\x00\x01binary")

    result = send_request(OutgoingRequest(method="GET", url="https://api.example.com/file.pdf"), resolve=public, transport=mock(handler))
    assert result.is_binary and result.body == "" and result.size_bytes > 0


def test_timeout_is_explained():
    def handler(request):
        raise httpx2.ReadTimeout("slow", request=request)

    result = send_request(OutgoingRequest(method="GET", url="https://api.example.com/slow"), resolve=public, transport=mock(handler))
    assert result.error_kind == "timeout"


def test_redact_url_masks_secret_query_params():
    assert redact_url("https://x.io/a?api_key=SECRET&page=2") == f"https://x.io/a?api_key={MASK}&page=2".replace("•", "%E2%80%A2")
    assert "SECRET" not in redact_url("https://user:SECRET@x.io/a")


def test_redact_body_handles_json_form_and_known_secrets():
    from app.http_runner.redact import redact_body

    assert "abc" not in redact_body('{"data": {"password": "abc", "name": "Acme"}}')
    assert "Acme" in redact_body('{"data": {"password": "abc", "name": "Acme"}}')
    assert "xyz" not in redact_body("grant_type=refresh_token&refresh_token=xyz")
    assert "MYTOKEN" not in redact_body("plain text mentioning MYTOKEN", ["MYTOKEN"])


def test_missing_reason_phrase_gets_standard_text():
    result = send_request(OutgoingRequest(method="GET", url="https://api.example.com/x"), resolve=public,
                          transport=mock(lambda r: httpx2.Response(204, extensions={"reason_phrase": b""})))
    assert result.reason == "No Content"
